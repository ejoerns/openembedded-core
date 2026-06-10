# genimage.bbclass
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
#   do_genimage[depends] += "virtual/bootloader:do_deploy core-image-minimal:do_image_complete"
#
# The main purpose of genimage is to create an entire SD, eMMC, NAND, or UBI
# image with multiple partitions based on different images (kernel,
# bootloader, rootfs, ...)
#
# The name of the resulting image is named the same way normal images are
# named. You can customize output with the variables `GENIMAGE_IMAGE_NAME` and
# `GENIMAGE_IMAGE_SUFFIX`.
#
# Note that you should also make your genimage image recipe depend on the set
# of host tools required for building, e.g.
#
#   DEPENDS += "e2fsprogs-native"
#
# You can also use genimage to split up a created rootfs into different
# partition images. Consider a yocto-created rootfs, for example.
# You can put all content of the /home directory in a 'data' partition while
# putting all content of /etc in a config partition and the rest ('/') in the
# final rootfs partition, then pack all them together to an SD image.
#
# In order to do this, you have to provide the name of the image recipe you
# intend to split up the data for:
#
#   GENIMAGE_ROOTFS_IMAGE = "my-production-image"
#
# The image recipe must build an archive, either `tar.bz2` (default) or the
# type matching the extension you set with `GENIMAGE_ROOTFS_IMAGE_FSTYPE`:
#
#   GENIMAGE_ROOTFS_IMAGE_FSTYPE = "tar.xz"
#
# Since nanbield the IMAGE_NAME also contains the IMAGE_NAME_SUFFIX, with it
# being set inside the image-artifact-names.bbclass. This is either '${IMAGE_NAME_SUFFIX}'
# (default) or the name matching the suffix you set with
# `GENIMAGE_ROOTFS_IMAGE_SUFFIX`:
#
#   GENIMAGE_ROOTFS_IMAGE_SUFFIX = ".rootfs"
#
# The split-up is controlled by your genimage config file, using the
# 'mountpoint' options:
#
#   datafs {
#     [...]
#     mountpoint = "/home"
#   }
#
#   rootfs {
#     [...]
#     mountpoint = "/"
#   }
#
# Most common variables for customization from image recipe:
#
# GENIMAGE_CONFIG	- config passed to genimage --config (default: 'genimage.config'). bitbake
# variables are expanded.
# GENIMAGE_IMAGE_SUFFIX	- file extension suffix for created image (default: '.img')
# GENIMAGE_ROOTFS_IMAGE - input rootfs image to generate file system images from
# GENIMAGE_ROOTFS_IMAGE_FSTYPE	- input roofs FSTYPE to use (default: 'tar.bz2')
# GENIMAGE_ROOTFS_IMAGE_SUFFIX	- IMAGE_NAME_SUFFIX to use (default: '${IMAGE_NAME_SUFFIX}')
# GENIMAGE_COMPRESSION - compress the generated image. Allowed values
# are 'none' for no compression (the default), 'gzip' and 'xz'.

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

GENIMAGE_CONFIG ?= "genimage.config"

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

# rootfs image to extract and use as rootpath
GENIMAGE_ROOTFS_IMAGE ?= ""
GENIMAGE_ROOTFS_IMAGE_FSTYPE ?= "${@get_default_fstype(d)}"
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
    infile = d.getVar('S') + "/" + d.getVar('GENIMAGE_CONFIG')
    outfile = d.getVar('B') + "/.config"

    with open(infile, "r") as input:
        content = input.read()

        if "GENIMAGE_IMAGE_FULLNAME" not in content:
            bb.note(f"{d.getVar('GENIMAGE_CONFIG')} does not contain ${{GENIMAGE_IMAGE_FULLNAME}}")

        expansion = d.expand(content)

    with open(outfile, "w") as output:
        output.write(expansion)
}

fakeroot do_genimage () {
    # unpack input rootfs image if given
    if [ "x${GENIMAGE_ROOTFS_IMAGE}" != "x" ]; then
        bbnote "Unpacking ${DEPLOY_DIR_IMAGE}/${GENIMAGE_ROOTFS_IMAGE}-${MACHINE}${GENIMAGE_ROOTFS_IMAGE_SUFFIX}.${GENIMAGE_ROOTFS_IMAGE_FSTYPE} to ${GENIMAGE_ROOTDIR}"
        tar -xf ${DEPLOY_DIR_IMAGE}/${GENIMAGE_ROOTFS_IMAGE}-${MACHINE}${GENIMAGE_ROOTFS_IMAGE_SUFFIX}.${GENIMAGE_ROOTFS_IMAGE_FSTYPE} -C ${GENIMAGE_ROOTDIR}
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

addtask genimage after do_unpack

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

# ---------------------------------------------------------------------------
# Optional runqemu integration
#
# Set GENIMAGE_RUNQEMU = "1" in your disk-image recipe to have the class
# generate a .qemuboot.conf alongside the disk image so that the recipe can
# be booted directly with:
#
#   runqemu <recipe-name> nographic
#
# Required QB_* settings for a fully self-booting disk image:
#
#   QB_DEFAULT_KERNEL = "none"          -- disk image contains its own kernel
#   QB_DEFAULT_BIOS   = "u-boot.bin"   -- firmware loaded by QEMU as -bios
#                                          (resolved relative to DEPLOY_DIR_IMAGE)
#
# The machine's QB_ROOTFS_OPT (e.g. the virtio-blk-pci drive defined in
# qemuarm64.conf) is reused as-is; @ROOTFS@ is replaced by runqemu with the
# path to the generated .img file.
# ---------------------------------------------------------------------------
GENIMAGE_RUNQEMU ?= "0"

# Default QB_* values when runqemu integration is enabled.
# Recipes may override any of these.
QB_DEFAULT_FSTYPE ?= "${@d.getVar('GENIMAGE_IMAGE_SUFFIX').lstrip('.')}"
QB_DEFAULT_KERNEL ?= "none"
QB_DEFAULT_BIOS   ?= ""

def _genimage_qemuboot_vars(d):
    build_vars = [
        'MACHINE', 'TUNE_ARCH', 'DEPLOY_DIR_IMAGE',
        'IMAGE_NAME', 'IMAGE_LINK_NAME',
        'STAGING_DIR_NATIVE', 'STAGING_BINDIR_NATIVE',
    ]
    return build_vars + [k for k in d.keys() if k.startswith('QB_')]

do_write_qemuboot_conf[vardeps] += "${@' '.join(_genimage_qemuboot_vars(d))}"
do_write_qemuboot_conf[vardepsexclude] += "TOPDIR"

python do_write_qemuboot_conf() {
    if d.getVar('GENIMAGE_RUNQEMU') != '1':
        return

    import configparser, os

    deploydir  = d.getVar('DEPLOYDIR')
    finalpath  = d.getVar('DEPLOY_DIR_IMAGE')
    topdir     = d.getVar('TOPDIR')
    image_name = d.getVar('IMAGE_NAME')
    link_name  = d.getVar('IMAGE_LINK_NAME')

    qemuboot      = os.path.join(deploydir, image_name + '.qemuboot.conf')
    qemuboot_link = os.path.join(deploydir, link_name  + '.qemuboot.conf') if link_name else ''

    cf = configparser.ConfigParser()
    cf.add_section('config_bsp')

    for k in sorted(_genimage_qemuboot_vars(d)):
        if ':' in k:
            continue
        # Point at the relocatable qemu-helper-native sysroot (not removed by rm_work)
        if k == 'STAGING_BINDIR_NATIVE':
            val = os.path.join(d.getVar('BASE_WORKDIR'), d.getVar('BUILD_SYS'),
                               'qemu-helper-native/1.0/recipe-sysroot-native/usr/bin/')
        else:
            val = d.getVar(k)
        if val is None:
            continue
        # Store paths relative to DEPLOY_DIR_IMAGE for relocatability
        if val.startswith(topdir):
            val = os.path.relpath(val, finalpath)
        cf.set('config_bsp', k, val)

    # Resolve QB_DEFAULT_KERNEL to the real filename (skip when "none")
    kernel = d.getVar('QB_DEFAULT_KERNEL') or 'none'
    if kernel != 'none':
        kernel_link = os.path.join(d.getVar('DEPLOY_DIR_IMAGE'), kernel)
        kernel = os.path.relpath(os.path.realpath(kernel_link), finalpath)
    cf.set('config_bsp', 'QB_DEFAULT_KERNEL', kernel)

    os.makedirs(deploydir, exist_ok=True)
    with open(qemuboot, 'w') as f:
        cf.write(f)

    if qemuboot_link and qemuboot_link != qemuboot:
        if os.path.lexists(qemuboot_link):
            os.remove(qemuboot_link)
        os.symlink(os.path.basename(qemuboot), qemuboot_link)

    bb.note("Written %s" % qemuboot)
}

addtask do_write_qemuboot_conf after do_genimage before do_deploy
