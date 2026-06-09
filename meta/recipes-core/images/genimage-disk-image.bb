# Note that this is NOT the root file system recipe and serves only for
# building the disk image!

LIC_FILES_CHKSUM = "file://${COREBASE}/meta/COPYING.MIT;md5=3da9cfbcb788c80a0384361b4de20420"

inherit genimage

SRC_URI += "file://genimage.config"

DEPENDS += "e2fsprogs-native"

ROOTFS_IMAGE_NAME ?= "core-image-minimal"

do_genimage[depends] += " \
    virtual/bootloader:do_deploy \
    ${ROOTFS_IMAGE_NAME}:do_image_complete \
"
