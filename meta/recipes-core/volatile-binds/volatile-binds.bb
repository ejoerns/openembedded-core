SUMMARY = "Volatile bind mount setup and configuration for read-only-rootfs"
DESCRIPTION = "${SUMMARY}"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://COPYING.MIT;md5=5750f3aa4ea2b00c2bf21b2b2a7b714d"

SRC_URI = "\
    file://mount.copybind \
    file://COPYING.MIT \
    file://volatile-binds.mount.in \
"

S = "${UNPACKDIR}"

inherit allarch systemd features_check

REQUIRED_DISTRO_FEATURES = "systemd"

VOLATILE_BINDS ?= "\
    ${localstatedir}/volatile/lib ${localstatedir}/lib\n\
    ${localstatedir}/volatile/cache ${localstatedir}/cache\n\
    ${localstatedir}/volatile/spool ${localstatedir}/spool\n\
    ${localstatedir}/volatile/srv /srv\n\
"
VOLATILE_BINDS[type] = "list"
VOLATILE_BINDS[separator] = "\n"

def volatile_systemd_units(d):
    units = []
    for line in oe.data.typed_value("VOLATILE_BINDS", d):
        if not line:
            continue
        what, where = line.split(None, 1)
        units.append("%s.mount" % where[1:].replace("/", "-"))
    return " ".join(units)

SYSTEMD_SERVICE:${PN} = "${@volatile_systemd_units(d)}"

FILES:${PN} += "${systemd_system_unitdir}/*.mount ${servicedir}"

# Set to 1 to forcibly skip OverlayFS, and default to copy+bind
AVOID_OVERLAYFS = "0"

do_compile () {
    while read spec mountpoint; do
        if [ -z "$spec" ]; then
            continue
        fi

        mountfile="$(echo "${mountpoint#/}" | tr / -).mount"
        [ "$mountpoint" != ${localstatedir}/lib ] || var_lib_mountfile=$mountfile
        sed -e "s#@what@#$spec#g; s#@where@#$mountpoint#g" \
            -e "s#@whatparent@#${spec%/*}#g; s#@whereparent@#${mountpoint%/*}#g" \
            -e "s#@options@#${@'x-avoid-overlayfs' if d.getVar('AVOID_OVERLAYFS') == '1' else 'defaults'}#g" \
            volatile-binds.mount.in >$mountfile
    done <<END
${@d.getVar('VOLATILE_BINDS').replace("\\n", "\n")}
END

    if [ -e "$var_lib_mountfile" ]; then
        # As the seed is stored under /var/lib, ensure that this mount unit
        # runs before systemd-random-seed.service
        sed -i -e "/^Before=/s/\$/ systemd-random-seed.service/" \
               -e "/^WantedBy=/s/\$/ systemd-random-seed.service/" \
               "$var_lib_mountfile"
    fi
}

do_install () {
    install -d ${D}${base_sbindir}
    install -d ${D}${servicedir}
    install -m 0755 mount.copybind ${D}${base_sbindir}/

    install -d ${D}${systemd_system_unitdir}
    for unit in ${SYSTEMD_SERVICE:${PN}}; do
        install -m 0644 $unit ${D}${systemd_system_unitdir}/
    done

    # Suppress attempts to process some tmpfiles that are not temporary.
    #
    install -d ${D}${sysconfdir}/tmpfiles.d ${D}${localstatedir}/cache
    ln -s /dev/null ${D}${sysconfdir}/tmpfiles.d/etc.conf
    ln -s /dev/null ${D}${sysconfdir}/tmpfiles.d/home.conf
}
