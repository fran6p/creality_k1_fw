# Virtual sdcard support (print files directly from a host g-code file)
#
# Copyright (C) 2018  Kevin O'Connor <kevin@koconnor.net>
#
# This file may be distributed under the terms of the GNU GPLv3 license.
import os, logging, io
from .tool import reportInformation

VALID_GCODE_EXTS = ['gcode', 'g', 'gco']
LAYER_KEYS = [";LAYER:", "; layer:", "; LAYER:", ";AFTER_LAYER_CHANGE", ";LAYER_CHANGE"]

class VirtualSD:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.printer.register_event_handler("klippy:shutdown",
                                            self.handle_shutdown)
        # sdcard state
        sd = config.get('path')
        self.sdcard_dirname = os.path.normpath(os.path.expanduser(sd))
        self.current_file = None
        self.file_position = self.file_size = 0
        # Print Stat Tracking
        self.print_stats = self.printer.load_object(config, 'print_stats')
        # Work timer
        self.reactor = self.printer.get_reactor()
        self.must_pause_work = self.cmd_from_sd = False
        self.next_file_position = 0
        self.work_timer = None
        # Error handling
        gcode_macro = self.printer.load_object(config, 'gcode_macro')
        self.on_error_gcode = gcode_macro.load_template(
            config, 'on_error_gcode', '')
        # Register commands
        self.gcode = self.printer.lookup_object('gcode')
        for cmd in ['M20', 'M21', 'M23', 'M24', 'M25', 'M26', 'M27']:
            self.gcode.register_command(cmd, getattr(self, 'cmd_' + cmd))
        for cmd in ['M28', 'M29', 'M30']:
            self.gcode.register_command(cmd, self.cmd_error)
        self.gcode.register_command(
            "SDCARD_RESET_FILE", self.cmd_SDCARD_RESET_FILE,
            desc=self.cmd_SDCARD_RESET_FILE_help)
        self.gcode.register_command(
            "SDCARD_PRINT_FILE", self.cmd_SDCARD_PRINT_FILE,
            desc=self.cmd_SDCARD_PRINT_FILE_help)
        self.count_G1 = 0 
        self.count_line = 0
        self.do_resume_status = False
        self.eepromWriteCount = 1
        self.fan_state = ""
        self.user_print_refer_path = "/usr/data/creality/userdata/config/user_print_refer.json"
        self.print_file_name_path = "/usr/data/creality/userdata/config/print_file_name.json"
        self.print_first_layer = False
        self.first_layer_stop = False
        self.count_M204 = 0
    def handle_shutdown(self):
        if self.work_timer is not None:
            self.must_pause_work = True
            try:
                readpos = max(self.file_position - 1024, 0)
                readcount = self.file_position - readpos
                self.current_file.seek(readpos)
                data = self.current_file.read(readcount + 128)
            except:
                logging.exception("virtual_sdcard shutdown read")
                return
            logging.info("Virtual sdcard (%d): %s\nUpcoming (%d): %s",
                         readpos, repr(data[:readcount]),
                         self.file_position, repr(data[readcount:]))
        self.print_first_layer = False
        self.first_layer_stop = False
        self.print_stats.power_loss = 0
        self.count_M204 = 0
    def stats(self, eventtime):
        if self.work_timer is None:
            return False, ""
        return True, "sd_pos=%d" % (self.file_position,)
    def get_file_list(self, check_subdirs=False):
        if check_subdirs:
            flist = []
            for root, dirs, files in os.walk(
                    self.sdcard_dirname, followlinks=True):
                for name in files:
                    ext = name[name.rfind('.')+1:]
                    if ext not in VALID_GCODE_EXTS:
                        continue
                    full_path = os.path.join(root, name)
                    r_path = full_path[len(self.sdcard_dirname) + 1:]
                    size = os.path.getsize(full_path)
                    flist.append((r_path, size))
            return sorted(flist, key=lambda f: f[0].lower())
        else:
            dname = self.sdcard_dirname
            try:
                filenames = os.listdir(self.sdcard_dirname)
                return [(fname, os.path.getsize(os.path.join(dname, fname)))
                        for fname in sorted(filenames, key=str.lower)
                        if not fname.startswith('.')
                        and os.path.isfile((os.path.join(dname, fname)))]
            except:
                logging.exception("virtual_sdcard get_file_list")
                raise self.gcode.error("Unable to get file list")
    def get_status(self, eventtime):
        return {
            'file_path': self.file_path(),
            'progress': self.progress(),
            'is_active': self.is_active(),
            'file_position': self.file_position,
            'file_size': self.file_size,
            'first_layer_stop':  self.first_layer_stop,
        }
    def file_path(self):
        if self.current_file:
            return self.current_file.name
        return None
    def progress(self):
        if self.file_size:
            return float(self.file_position) / self.file_size
        else:
            return 0.
    def is_active(self):
        return self.work_timer is not None
    def do_pause(self):
        if self.work_timer is not None:
            self.must_pause_work = True
            while self.work_timer is not None and not self.cmd_from_sd:
                self.reactor.pause(self.reactor.monotonic() + .001)
    def do_resume(self):
        if self.work_timer is not None:
            raise self.gcode.error("SD busy")
        self.must_pause_work = False
        self.work_timer = self.reactor.register_timer(
            self.work_handler, self.reactor.NOW)
    def do_cancel(self):
        self.print_stats.power_loss = 0
        self.first_layer_stop = False
        self.print_first_layer = False
        self.count_M204 = 0
        if self.current_file is not None:
            self.do_pause()
            self.current_file.close()
            self.current_file = None
            self.print_stats.note_cancel()
        self.file_position = self.file_size = 0.
        from subprocess import call
        if os.path.exists(self.print_file_name_path):
            os.remove(self.print_file_name_path)
        call("sync", shell=True)
        try:
            import json
            power_loss_switch = False
            if os.path.exists(self.user_print_refer_path):
                with open(self.user_print_refer_path, "r") as f:
                    data = json.loads(f.read())
                    power_loss_switch = data.get("power_loss", {}).get("switch", False)
            bl24c16f = self.printer.lookup_object('bl24c16f') if "bl24c16f" in self.printer.objects else None
            if power_loss_switch and bl24c16f:
                bl24c16f.setEepromDisable()
                # self.gcode.run_script("EEPROM_WRITE_BYTE ADDR=1 VAL=255")
        except Exception as err:
            pass
    # G-Code commands
    def cmd_error(self, gcmd):
        raise gcmd.error("SD write not supported")
    def _reset_file(self):
        if self.current_file is not None:
            self.do_pause()
            self.current_file.close()
            self.current_file = None
        self.file_position = self.file_size = 0.
        self.print_stats.reset()
        self.printer.send_event("virtual_sdcard:reset_file")
    cmd_SDCARD_RESET_FILE_help = "Clears a loaded SD File. Stops the print "\
        "if necessary"
    def cmd_SDCARD_RESET_FILE(self, gcmd):
        if self.cmd_from_sd:
            raise gcmd.error(
                "SDCARD_RESET_FILE cannot be run from the sdcard")
        self._reset_file()
    cmd_SDCARD_PRINT_FILE_help = "Loads a SD file and starts the print.  May "\
        "include files in subdirectories."
    def cmd_SDCARD_PRINT_FILE(self, gcmd):
        if self.work_timer is not None:
            raise gcmd.error("SD busy")
        self._reset_file()
        filename = gcmd.get("FILENAME")
        first_floor = gcmd.get("FIRST_FLOOR_PRINT", None)
        if first_floor is None or first_floor == False:
            self.print_first_layer = False
        else:
            self.print_first_layer = True
        if filename[0] == '/':
            filename = filename[1:]
        self._load_file(gcmd, filename, check_subdirs=True)
        self.do_resume()
    def cmd_M20(self, gcmd):
        # List SD card
        files = self.get_file_list()
        gcmd.respond_raw("Begin file list")
        for fname, fsize in files:
            gcmd.respond_raw("%s %d" % (fname, fsize))
        gcmd.respond_raw("End file list")
    def cmd_M21(self, gcmd):
        # Initialize SD card
        gcmd.respond_raw("SD card ok")
    def cmd_M23(self, gcmd):
        # Select SD file
        if self.work_timer is not None:
            raise gcmd.error("SD busy")
        self._reset_file()
        filename = gcmd.get_raw_command_parameters().strip()
        if filename.startswith('/'):
            filename = filename[1:]
        self._load_file(gcmd, filename)
    def _load_file(self, gcmd, filename, check_subdirs=False):
        files = self.get_file_list(check_subdirs)
        flist = [f[0] for f in files]
        files_by_lower = { fname.lower(): fname for fname, fsize in files }
        fname = filename
        try:
            if fname not in flist:
                fname = files_by_lower[fname.lower()]
            fname = os.path.join(self.sdcard_dirname, fname)
            f = io.open(fname, 'r', newline='')
            f.seek(0, os.SEEK_END)
            fsize = f.tell()
            f.seek(0)
        except:
            logging.exception("virtual_sdcard file open")
            raise gcmd.error("""{"code":"key121", "msg": "Unable to open file", "values": []}""")
        gcmd.respond_raw("File opened:%s Size:%d" % (filename, fsize))
        gcmd.respond_raw("File selected")
        self.current_file = f
        self.file_position = 0
        self.file_size = fsize
        self.print_stats.set_current_file(filename)
    def cmd_M24(self, gcmd):
        # Start/resume SD print
        self.do_resume()
    def cmd_M25(self, gcmd):
        # Pause SD print
        self.do_pause()
    def cmd_M26(self, gcmd):
        # Set SD position
        if self.work_timer is not None:
            raise gcmd.error("SD busy")
        pos = gcmd.get_int('S', minval=0)
        self.file_position = pos
    def cmd_M27(self, gcmd):
        # Report SD print status
        if self.current_file is None:
            gcmd.respond_raw("Not SD printing.")
            return
        gcmd.respond_raw("SD printing byte %d/%d"
                         % (self.file_position, self.file_size))
    def get_file_position(self):
        return self.next_file_position
    def set_file_position(self, pos):
        self.next_file_position = pos
    def is_cmd_from_sd(self):
        return self.cmd_from_sd
    def tail_read(self, f):
        cur_pos = f.tell()
        buf = ''
        while True:
            b = str(f.read(1))
            buf = b + buf
            cur_pos -= 1
            if cur_pos < 0: break
            f.seek(cur_pos)
            if b.startswith("\n") or b.startswith("\r"):
                buf = '\n'
            if (buf.startswith("G1") or buf.startswith("G0") or buf.startswith(";")) and buf.endswith("\n"):
                break
        return buf
    def getXYZE(self, file_path, file_position):
        result = {"X": 0, "Y": 0, "Z": 0, "E": 0}
        try:
            import io, time
            with io.open(file_path, "r", encoding="utf-8") as f:
                f.seek(file_position)
                while True:
                    cur_pos = f.tell()
                    if cur_pos<=0:
                        break
                    line = self.tail_read(f)
                    line_list = line.split(" ")
                    if not result["E"] and "E" in line:
                        for obj in line_list:
                            if obj.startswith("E"):
                                ret = obj[1:].split("\r")[0]
                                ret = ret.split("\n")[0]
                                if ret.startswith("."):
                                    result["E"] = float(("0"+ret.strip(" ")))
                                else:
                                    result["E"] = float(ret.strip(" "))
                    if not result["X"] and not result["Y"]:
                        for obj in line_list:
                            if obj.startswith("X"):
                                logging.info("power_loss getXYZE X:%s" % obj)
                                result["X"] = float(obj.split("\r")[0][1:])
                            if obj.startswith("Y"):
                                logging.info("power_loss getXYZE Y:%s" % obj)
                                result["Y"] = float(obj.split("\r")[0][1:])
                    if not result["Z"] and "Z" in line:
                        for obj in line_list:
                            if obj.startswith("Z"):
                                logging.info("power_loss getXYZE Z:%s" % obj)
                                result["Z"] = float(obj.split("\r")[0][1:])
                    if result["X"] and result["Y"] and result["Z"] and result["E"]:
                        logging.info("get XYZE:%s" % str(result))
                        logging.info("power_loss get XYZE:%s" % str(result))
                        break
                    time.sleep(0.001)
        except Exception as err:
            logging.exception(err)
        return result
    def get_print_temperature(self, file_path):
        import json
        bed = 0
        extruder = 202.0
        if os.path.exists(self.gcode.last_temperature_info):
            try:
                with open(self.gcode.last_temperature_info, "r") as f:
                    result = f.read()
                    if len(result) > 0:
                        result = json.loads(result)
                        bed = float(result.get("bed", 0))
                        extruder = float(result.get("extruder", 201.0))
            except Exception as err:
                logging.error("get_print_temperature: %s" % err)
        logging.info("power_loss get_print_temperature: bed:%s, extruder:%s" % (bed, extruder))
        return bed, extruder

    # Background work timer
    def work_handler(self, eventtime):
        reportInformation("Start print, filename:%s" % self.current_file.name)
        logging.info("work_handler start print, filename:%s" % self.current_file.name)
        self.print_stats.note_start()
        import json, time
        from subprocess import check_output
        self.count_line = 0
        self.count_G1 = 0 
        self.eepromWriteCount = 1
        gcode_move = self.printer.lookup_object('gcode_move', None)
        try:
            if os.path.exists(self.user_print_refer_path):
                with open(self.user_print_refer_path, "r") as f:
                    data = json.loads(f.read())
                    delay_photography_switch = data.get("delay_image", {}).get("switch", 1)
                    location = data.get("delay_image", {}).get("location", 0)
                    frame = data.get("delay_image", {}).get("frame", 15)
                    interval = data.get("delay_image", {}).get("interval", 1)
                    power_loss_switch = data.get("power_loss", {}).get("switch", False)
        except Exception as err:
            delay_photography_switch = 1
            location = 0
            frame = 15
            interval = 1
            power_loss_switch = False
        logging.info("delay_photography status: delay_photography_switch:%s, location:%s, frame:%s, interval:%s" % (
            delay_photography_switch, location, frame, interval
        ))
        bl24c16f = self.printer.lookup_object('bl24c16f') if "bl24c16f" in self.printer.objects and power_loss_switch else None
        eepromState = True
        try:
            sameFileName = False
            if os.path.exists(self.print_file_name_path):
                with open(self.print_file_name_path, "r") as f:
                    result = (json.loads(f.read()))
                    if result.get("file_path", "") == self.current_file.name:
                        sameFileName = True
                    else:
                        # clear power_loss info
                        os.remove(self.print_file_name_path)
                        if power_loss_switch and bl24c16f:
                            bl24c16f.setEepromDisable()
            eepromState = bl24c16f.checkEepromFirstEnable() if power_loss_switch and bl24c16f else True
            if power_loss_switch and bl24c16f and not self.do_resume_status and sameFileName and not eepromState:
                logging.info("power_loss start do_resume...")
                logging.info("power_loss start print, filename:%s" % self.current_file.name)
                pos = bl24c16f.eepromReadHeader()
                logging.info("power_loss pos:%s" % pos)
                print_info = bl24c16f.eepromReadBody(pos)
                logging.info("power_loss print_info:%s" % str(print_info))
                self.file_position = int(print_info.get("file_position", 0))
                logging.info("power_loss file_position:%s" % self.file_position)
                gcode = self.printer.lookup_object('gcode')
                temperature = self.get_print_temperature(self.current_file.name)
                gcode.run_script("M140 S%s" % temperature[0])
                gcode.run_script("M109 S%s" % temperature[1])
                XYZE = self.getXYZE(self.current_file.name, self.file_position)
                logging.info("power_loss XYZE:%s, file_position:%s  " % (str(XYZE), self.file_position))
                if XYZE.get("Z") == 0:
                    logging.error("power_loss gcode Z == 0 err-------------------------------------------")
                    from subprocess import call
                    if os.path.exists(self.print_file_name_path):
                        os.remove(self.print_file_name_path)
                    call("sync", shell=True)
                    try:
                        import json
                        power_loss_switch = False
                        if os.path.exists(self.user_print_refer_path):
                            with open(self.user_print_refer_path, "r") as f:
                                data = json.loads(f.read())
                                power_loss_switch = data.get("power_loss", {}).get("switch", False)
                        bl24c16f = self.printer.lookup_object('bl24c16f') if "bl24c16f" in self.printer.objects else None
                        if power_loss_switch and bl24c16f:
                            bl24c16f.setEepromDisable()
                    except Exception as err:
                        logging.error("power_loss gcode Z == 0: %s" % err)
                    error_message = "power_loss gcode Z == 0, stop print"
                    self.print_stats.note_error(error_message)
                    raise
                gcode_move.cmd_CX_RESTORE_GCODE_STATE(print_info, self.print_file_name_path, XYZE)
                logging.info("power_loss end do_resume success")
                self.print_stats.power_loss = 0
            else:
                self.gcode.run_script("G90")
        except Exception as err:
            self.print_stats.power_loss = 0
            logging.exception("work_handler RESTORE_GCODE_STATE error: %s" % err)
        if power_loss_switch and bl24c16f:
            gcode_move.recordPrintFileName(self.print_file_name_path, self.current_file.name)
        logging.info("Starting SD card print (position %d)", self.file_position)
        self.reactor.unregister_timer(self.work_timer)
        try:
            self.current_file.seek(self.file_position)
        except:
            logging.exception("virtual_sdcard seek")
            self.work_timer = None
            return self.reactor.NEVER
        # self.print_stats.note_start()
        gcode_mutex = self.gcode.get_mutex()
        partial_input = ""
        lines = []
        error_message = None
        lastE = 0
        layer_count = 0
        # self.gcode.run_script("G90")
        toolhead = self.printer.lookup_object('toolhead')
        while not self.must_pause_work:
            if not lines:
                # Read more data
                try:
                    data = self.current_file.read(8192)
                except:
                    logging.exception("virtual_sdcard read")
                    break
                if not data:
                    # End of file
                    reportInformation("Finished print success, filename:%s" % self.current_file.name)
                    self.current_file.close()
                    self.current_file = None
                    logging.info("Finished SD card print")
                    self.gcode.respond_raw("Done printing file")
                    if os.path.exists(self.print_file_name_path):
                        os.remove(self.print_file_name_path)
                    if power_loss_switch and bl24c16f:
                        self.gcode.run_script("EEPROM_WRITE_BYTE ADDR=1 VAL=255")
                    self.first_layer_stop = False
                    self.print_first_layer = False
                    self.count_M204 = 0
                    break
                lines = data.split('\n')
                lines[0] = partial_input + lines[0]
                partial_input = lines.pop()
                lines.reverse()
                self.reactor.pause(self.reactor.NOW)
                continue
            # Pause if any other request is pending in the gcode class
            if gcode_mutex.test():
                self.reactor.pause(self.reactor.monotonic() + 0.100)
                continue
            # Dispatch command
            self.cmd_from_sd = True
            line = lines.pop()
            next_file_position = self.file_position + len(line) + 1
            self.next_file_position = next_file_position
            try:
                if power_loss_switch and bl24c16f and self.count_G1 >= 20 and self.count_line % 100 == 0:
                    base_position_e = round(list(gcode_move.base_position)[-1], 2)
                    pos = bl24c16f.eepromReadHeader()
                    if eepromState:
                        # eeprom first enable
                        self.gcode.run_script("EEPROM_WRITE_BYTE ADDR=1 VAL=1")
                        self.gcode.run_script("EEPROM_WRITE_INT ADDR=%s VAL=%s" % (pos*8, self.file_position))
                        self.gcode.run_script("EEPROM_WRITE_FLOAT ADDR=%s VAL=%s" % (pos*8+4, base_position_e))
                        self.gcode.run_script("EEPROM_WRITE_BYTE ADDR=0 VAL=%d" % pos)
                        eepromState = False
                    else:
                        # pos = bl24c16f.eepromReadHeader()
                        if self.eepromWriteCount < 256:
                            self.gcode.run_script("EEPROM_WRITE_INT ADDR=%s VAL=%s" % (pos*8, self.file_position))
                            self.gcode.run_script("EEPROM_WRITE_FLOAT ADDR=%s VAL=%s" % (pos*8+4, base_position_e))
                        else:
                            self.eepromWriteCount = 1
                            pos += 1
                            if pos == 256:
                                pos = 1
                            self.gcode.run_script("EEPROM_WRITE_INT ADDR=%s VAL=%s" % (pos*8, self.file_position))
                            self.gcode.run_script("EEPROM_WRITE_FLOAT ADDR=%s VAL=%s" % (pos*8+4, base_position_e))
                            self.gcode.run_script("EEPROM_WRITE_BYTE ADDR=0 VAL=%d" % pos)
                        # logging.info("eepromWriteCount:%d, pos:%d" % (self.eepromWriteCount, pos))
                    self.eepromWriteCount += 1
                if power_loss_switch and bl24c16f and self.count_G1 == 19:
                    gcode_move.recordPrintFileName(self.print_file_name_path, self.current_file.name, fan_state=self.fan_state)
                if power_loss_switch and bl24c16f and self.count_line % 999 == 0:
                    gcode_move.recordPrintFileName(self.print_file_name_path, self.current_file.name, fan_state=self.fan_state)
                if line.startswith("G1") and "E" in line:
                    try:
                        E_str = line.split(" ")[-1]
                        if E_str.startswith("E"):
                            lastE = float(E_str.strip("\r").strip("\n")[1:])
                    except Exception as err:
                        pass
                elif line.startswith("M106"):
                    self.fan_state = line.strip("\r").strip("\n")
                    if power_loss_switch and bl24c16f:
                        gcode_move.recordPrintFileName(self.print_file_name_path, self.current_file.name, fan_state=self.fan_state)
                    self.fan_state = ""
                
                if self.print_first_layer and self.count_G1 >= 20:
                    for layer_key in LAYER_KEYS:
                        if line.startswith(layer_key):
                            logging.info("print_first_layer layer_key:%s" % layer_key)
                            X, Y, Z, E = toolhead.get_position()
                            self.gcode.run_script("PAUSE")
                            self.first_layer_stop = True
                if delay_photography_switch:
                    for layer_key in LAYER_KEYS:
                        if ";LAYER_COUNT:" in layer_key:
                            break
                        if line.startswith(layer_key):
                            if layer_count % int(interval) == 0:
                                if location:
                                    cmd_wait_for_stepper = "M400"
                                    # toolhead = self.printer.lookup_object('toolhead')
                                    X, Y, Z, E = toolhead.get_position()
                                    if self.count_G1 >= 20:
                                        # 1. Pull back and lift first
                                        logging.info("G1 F2400 E%s" % (lastE-3))
                                        logging.info(cmd_wait_for_stepper)
                                        self.gcode.run_script("G1 F2400 E%s" % (lastE-3))
                                        self.gcode.run_script(cmd_wait_for_stepper)
                                        time.sleep(0.1)
                                        self.gcode.run_script("G1 F3000 Z%s" % (Z + 2))
                                        self.gcode.run_script(cmd_wait_for_stepper)
                                        time.sleep(0.1)
                                        # 2. move to the specified position
                                        cmd = "G0 X5 Y150 F15000"
                                        logging.info(cmd)
                                        logging.info(cmd_wait_for_stepper)
                                        self.gcode.run_script(cmd)
                                        self.gcode.run_script(cmd_wait_for_stepper)
                                        try:
                                            capture_shell = "capture 0"
                                            logging.info(capture_shell)
                                            capture_ret = check_output(capture_shell, shell=True).decode("utf-8")
                                            logging.info("capture 0 return:#%s#" % str(capture_ret))
                                        except Exception as err:
                                            logging.error(err)
                                        time.sleep(0.1)
                                        # 3. move back
                                        move_back_cmd = "G0 X%s Y%s F15000" % (X, Y)
                                        logging.info(move_back_cmd)
                                        logging.info(cmd_wait_for_stepper)
                                        self.gcode.run_script(move_back_cmd)
                                        self.gcode.run_script(cmd_wait_for_stepper)
                                        time.sleep(0.2)
                                        self.gcode.run_script("G1 F3000 Z%s" % Z)
                                        self.gcode.run_script(cmd_wait_for_stepper)
                                        time.sleep(0.1)
                                        logging.info("G1 F2400 E%s" % (lastE))
                                        self.gcode.run_script("G1 F2400 E%s" % (lastE))
                                else:
                                    try:
                                        capture_shell = "capture 0"
                                        logging.info(capture_shell)
                                        capture_ret = check_output(capture_shell, shell=True).decode("utf-8")
                                        logging.info("capture 0 return:#%s#" % str(capture_ret))
                                    except Exception as err:
                                        logging.error(err)
                            layer_count += 1
                            break
                self.gcode.run_script(line)
                self.count_line += 1
                if self.count_G1 < 20 and line.startswith("G1"):
                    self.count_G1 += 1
            except self.gcode.error as e:
                error_message = str(e)
                try:
                    self.gcode.run_script(self.on_error_gcode.render())
                except:
                    logging.exception("virtual_sdcard on_error")
                break
            except:
                logging.exception("virtual_sdcard dispatch")
                break
            self.cmd_from_sd = False
            self.file_position = self.next_file_position
            # Do we need to skip around?
            if self.next_file_position != next_file_position:
                try:
                    self.current_file.seek(self.file_position)
                except:
                    logging.exception("virtual_sdcard seek")
                    self.work_timer = None
                    return self.reactor.NEVER
                lines = []
                partial_input = ""
        reportInformation("Exiting SD card print (position %d)" % self.file_position)
        logging.info("Exiting SD card print (position %d)", self.file_position)
        self.count_line = 0
        self.count_G1 = 0
        self.do_resume_status = False
        self.eepromWriteCount = 1
        self.work_timer = None
        self.cmd_from_sd = False
        if error_message is not None:
            self.print_stats.note_error(error_message)
        elif self.current_file is not None:
            self.print_stats.note_pause()
        else:
            self.print_stats.note_complete()
        return self.reactor.NEVER

def load_config(config):
    return VirtualSD(config)