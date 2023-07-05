#!/bin/sh

# LICENSE: MIT
# orginal creator: avx
# date: 05.07.2023

FW_NAME="CR4CU220812S11_ota_img_V"
FW_VER="1.2.9"
FW_IN=15
FW_OUT=22

PASSWORD="qH5i25Vd0kiFQl4B"

7z x -p${PASSWORD} ${FW_NAME}${FW_VER}.${FW_IN}.img

mv ${FW_NAME}${FW_VER}.${FW_IN} ${FW_NAME}${FW_VER}.${FW_OUT}
mv ${FW_NAME}${FW_VER}.${FW_OUT}/ota_v${FW_VER}.${FW_IN} ${FW_NAME}${FW_VER}.${FW_OUT}/ota_v${FW_VER}.${FW_OUT}
mv ${FW_NAME}${FW_VER}.${FW_OUT}/ota_v${FW_VER}.${FW_OUT}/ota_v${FW_VER}.${FW_IN}.ok ${FW_NAME}${FW_VER}.${FW_OUT}/ota_v${FW_VER}.${FW_OUT}/ota_v${FW_VER}.${FW_OUT}.ok

for OTA_FILE in \
        ${FW_NAME}${FW_VER}.${FW_OUT}/ota_config.in \
        ${FW_NAME}${FW_VER}.${FW_OUT}/ota_v${FW_VER}.${FW_OUT}/ota_update.in
do
    sed -i "s/${FW_VER}.${FW_IN}/${FW_VER}.${2}/g" ${OTA_FILE}
done

7z a -mhe=on -p${PASSWORD} ${FW_NAME}${FW_VER}.${FW_OUT}.7z ${FW_NAME}${FW_VER}.${FW_OUT}/*
mv ${FW_NAME}${FW_VER}.${FW_OUT}.7z ${FW_NAME}${FW_VER}.${FW_OUT}.img
