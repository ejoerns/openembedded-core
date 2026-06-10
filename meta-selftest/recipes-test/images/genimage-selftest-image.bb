SUMMARY = "Minimal genimage image for oe-selftest"
LIC_FILES_CHKSUM = "file://${COREBASE}/meta/COPYING.MIT;md5=3da9cfbcb788c80a0384361b4de20420"

inherit genimage

SRC_URI += " \
    file://genimage.config \
    file://genimage-redundant-rootfs.config \
    file://genimage-rootfs-split.config \
"

do_genimage[depends] += "core-image-minimal:do_image_complete"

include test_recipe.inc
