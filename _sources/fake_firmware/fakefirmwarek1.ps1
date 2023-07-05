# LICENSE: MIT
# by: KorayA >> https://www.reddit.com/user/KorayA
# original creator: avx
# date: 05.07.2023

# Check if 7z is available
if (-not (Get-Command "7z" -ErrorAction SilentlyContinue)) {
    Write-Host "7z is not available in the PATH. Please install 7-Zip and ensure it is added to the PATH."
    Read-Host -Prompt "Press Enter to exit"
    exit 1
}

$FW_NAME = "CR4CU220812S11_ota_img_V"
$FW_VER = "1.2.9"
$FW_IN = "15"
$FW_OUT = "22"

$PASSWORD = "qH5i25Vd0kiFQl4B"

& 7z x -p$PASSWORD ${FW_NAME}${FW_VER}.${FW_IN}.img

Move-Item ${FW_NAME}${FW_VER}.${FW_IN} ${FW_NAME}${FW_VER}.${FW_OUT}
Move-Item ${FW_NAME}${FW_VER}.${FW_OUT}/ota_v${FW_VER}.${FW_IN} ${FW_NAME}${FW_VER}.${FW_OUT}/ota_v${FW_VER}.${FW_OUT}
Move-Item ${FW_NAME}${FW_VER}.${FW_OUT}/ota_v${FW_VER}.${FW_OUT}/ota_v${FW_VER}.${FW_IN}.ok ${FW_NAME}${FW_VER}.${FW_OUT}/ota_v${FW_VER}.${FW_OUT}/ota_v${FW_VER}.${FW_OUT}.ok

$files = @(
    "${FW_NAME}${FW_VER}.${FW_OUT}/ota_config.in",
    "${FW_NAME}${FW_VER}.${FW_OUT}/ota_v${FW_VER}.${FW_OUT}/ota_update.in"
)

foreach ($file in $files) {
    (Get-Content $file) -replace "${FW_VER}.${FW_IN}", "${FW_VER}.${2}" | Set-Content $file
}

& 7z a -mhe=on -p$PASSWORD ${FW_NAME}${FW_VER}.${FW_OUT}.7z ${FW_NAME}${FW_VER}.${FW_OUT}/*
Move-Item ${FW_NAME}${FW_VER}.${FW_OUT}.7z ${FW_NAME}${FW_VER}.${FW_OUT}.img
