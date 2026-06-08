#
# Copyright OpenEmbedded Contributors
#
# SPDX-License-Identifier: MIT
#

#
# Class to generate file system and disk images using the `genimage` tool.
#
# In order to build images with this class, you need to create a dedicated disk
# image recipe! This must inherit the genimage class and have a valid genimage
# configuration file in SRC_URI (named `genimage.config` by default):
#
#   inherit genimage
#
#   SRC_URI += "file://genimage.config"
#
# You also need to depend on all recipes creating artifacts used by
# genimage to build the final (disk) image, e.g.:
#
#   do_genimage[depends] += "\
#       virtual/bootloader:do_deploy \
#       core-image-minimal:do_image_complete"
#

# Most common variables for customization from image recipe:
GENIMAGE_ROOTFS_IMAGE[doc] = "input rootfs archive to generate file system images from"
GENIMAGE_ROOTFS_IMAGE_FSTYPE[doc] = "input roofs FSTYPE to use (default: 'tar.bz2')"
GENIMAGE_ROOTFS_IMAGE_SUFFIX[doc] = "IMAGE_NAME_SUFFIX of the rootfs recipe (default: '.rootfs')"
GENIMAGE_IMAGE_FULLNAME[doc] = "file name of generated disk image. To be used as variable in genimage.config"
GENIMAGE_IMAGE_SUFFIX[doc] = "file extension suffix for created image (default: '.img')"
GENIMAGE_COMPRESSION[doc] = "compress the generated image. Allowed values are 'none' for no compression (the default), 'gzip' and 'xz'."

inherit nopackages image-artifact-names deploy

LICENSE ?= "MIT"
PACKAGES = ""
DEPENDS += "genimage-native"

INHIBIT_DEFAULT_DEPS = "1"

PACKAGE_ARCH = "${MACHINE_ARCH}"

python () {
    if bb.data.inherits_class('image', d):
        bb.fatal("genimage.bbclass is not designed to be inherited by a rootfs image recipe!")
}

S = "${UNPACKDIR}"
B = "${WORKDIR}/genimage-${PN}"

GENIMAGE_CONFIG_NAME ?= "genimage.config"

GENIMAGE_IMAGE_SUFFIX ?= ".img"

IMAGE_NAME_SUFFIX ?= ""
GENIMAGE_IMAGE_FULLNAME ?= "${IMAGE_NAME}${GENIMAGE_IMAGE_SUFFIX}"
GENIMAGE_IMAGE_LINK_FULLNAME ?= "${IMAGE_LINK_NAME}${GENIMAGE_IMAGE_SUFFIX}"

def get_default_fstype(d):
    fstypes = (d.getVar('IMAGE_FSTYPES') or '').split()
    for x in fstypes:
        if "tar" in x:
            return x
    return "tar.bz2"

# image recipe name of rootfs tar to extract and use as rootpath
GENIMAGE_ROOTFS_IMAGE ??= ""
GENIMAGE_ROOTFS_IMAGE_FSTYPE ?= ".${@get_default_fstype(d)}"
GENIMAGE_ROOTFS_IMAGE_SUFFIX ?= ".rootfs"

do_genimage[depends] += "${@'${GENIMAGE_ROOTFS_IMAGE}:do_image_complete' if '${GENIMAGE_ROOTFS_IMAGE}' else ''}"

# bmap generation
GENIMAGE_CREATE_BMAP ?= "0"
do_genimage[depends] += "${@'bmaptool-native:do_populate_sysroot' if d.getVar('GENIMAGE_CREATE_BMAP') == '1' else ''}"

# compression support
GENIMAGE_COMPRESSION ??= "none"

GENIMAGE_COMPRESS_DEPENDS[none] = ""
GENIMAGE_COMPRESS_DEPENDS[gzip] = "pigz-native:do_populate_sysroot"
GENIMAGE_COMPRESS_DEPENDS[xz]   = "xz-native:do_populate_sysroot"
do_genimage[depends] += "${@d.getVarFlag('GENIMAGE_COMPRESS_DEPENDS', '${GENIMAGE_COMPRESSION}')}"

GENIMAGE_COMPRESS_CMD[none] = ":"
GENIMAGE_COMPRESS_CMD[gzip] = "gzip -f -9 -n"
GENIMAGE_COMPRESS_CMD[xz]   = "xz -f"
GENIMAGE_COMPRESS_CMD = "${@d.getVarFlag('GENIMAGE_COMPRESS_CMD', '${GENIMAGE_COMPRESSION}')}"

GENIMAGE_TMPDIR  = "${WORKDIR}/genimage-tmp"
GENIMAGE_ROOTDIR  = "${WORKDIR}/root"

# additional options to pass to the genimage call
GENIMAGE_EXTRA_OPTS ??= ""

do_genimage_preprocess[cleandirs] = "${GENIMAGE_TMPDIR} ${GENIMAGE_ROOTDIR} ${B}"
do_genimage_preprocess[dirs] = "${B}"

python do_genimage_preprocess () {
    infile = d.getVar('S') + "/" + d.getVar('GENIMAGE_CONFIG_NAME')
    outfile = d.getVar('B') + "/.config"

    with open(infile, "r") as input:
        content = input.read()

        if "GENIMAGE_IMAGE_FULLNAME" not in content:
            bb.note(f"{d.getVar('GENIMAGE_CONFIG_NAME')} does not contain ${{GENIMAGE_IMAGE_FULLNAME}}")

        expansion = d.expand(content)

    with open(outfile, "w") as output:
        output.write(expansion)
}

GENIMAGE_ROOTFS_ARCHIVE_NAME ?= "${GENIMAGE_ROOTFS_IMAGE}${IMAGE_MACHINE_SUFFIX}${GENIMAGE_ROOTFS_IMAGE_SUFFIX}${GENIMAGE_ROOTFS_IMAGE_FSTYPE}"

PSEUDO_INCLUDE_PATHS .= ",${GENIMAGE_ROOTDIR},${GENIMAGE_TMPDIR}"

fakeroot do_genimage () {
    # unpack input rootfs image if given
    if [ "x${GENIMAGE_ROOTFS_IMAGE}" != "x" ]; then
        bbnote "Unpacking ${DEPLOY_DIR_IMAGE}/${GENIMAGE_ROOTFS_ARCHIVE_NAME} to ${GENIMAGE_ROOTDIR}"
        tar -xf ${DEPLOY_DIR_IMAGE}/${GENIMAGE_ROOTFS_ARCHIVE_NAME} -C ${GENIMAGE_ROOTDIR}
    fi

    genimage \
        --loglevel 2 \
        --config ${B}/.config \
        --tmppath ${GENIMAGE_TMPDIR} \
        --inputpath ${DEPLOY_DIR_IMAGE} \
        --includepath ${S} \
        --outputpath ${B} \
        --rootpath ${GENIMAGE_ROOTDIR} \
        ${GENIMAGE_EXTRA_OPTS}

    if [ "${GENIMAGE_CREATE_BMAP}" = 1 ] ; then
        bmaptool create -o ${B}/${GENIMAGE_IMAGE_FULLNAME}.bmap ${B}/${GENIMAGE_IMAGE_FULLNAME}
    fi

    ${GENIMAGE_COMPRESS_CMD} ${B}/${GENIMAGE_IMAGE_FULLNAME}

    rm ${B}/.config
}
do_genimage[depends] += "virtual/fakeroot-native:do_populate_sysroot"
do_genimage[prefuncs] += "do_genimage_preprocess"
SSTATE_SKIP_CREATION:task-genimage = '1'

addtask genimage after do_prepare_recipe_sysroot do_unpack

do_deploy () {
    find ${B} -maxdepth 1 -type f -exec install -m 0644 {} ${DEPLOYDIR}/ \;

    for img in ${B}/*; do
        [ -f "$img" ] || continue
        img=$(basename "${img}")
        case "$img" in *"${GENIMAGE_IMAGE_FULLNAME}"*)
            ln -sf ${img} \
                ${DEPLOYDIR}/$(echo "${img}" | sed "s/${GENIMAGE_IMAGE_FULLNAME}/${GENIMAGE_IMAGE_LINK_FULLNAME}/g")
        esac
    done
}

addtask deploy after do_genimage before do_build

do_patch[noexec] = "1"
do_configure[noexec] = "1"
do_compile[noexec] = "1"
do_install[noexec] = "1"
deltask do_populate_lic
deltask do_populate_sysroot
