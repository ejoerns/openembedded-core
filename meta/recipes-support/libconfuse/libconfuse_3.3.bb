SUMMARY = "libConfuse is a configuration file parser library"
HOMEPAGE = "https://github.com/libconfuse/libconfuse"
LICENSE = "ISC"
LIC_FILES_CHKSUM = "file://LICENSE;md5=42fa47330d4051cd219f7d99d023de3a"

SRC_URI = "${GITHUB_BASE_URI}/download/v${PV}/confuse-${PV}.tar.gz \
           file://0001-only-apply-search-path-logic-to-relative-pathnames.patch \
           file://CVE-2022-40320.patch"
SRC_URI[sha256sum] = "3a59ded20bc652eaa8e6261ab46f7e483bc13dad79263c15af42ecbb329707b8"

GITHUB_BASE_URI = "https://github.com/libconfuse/libconfuse/releases"
UPSTREAM_CHECK_REGEX = "releases/tag/v?(?P<pver>\d+\.\d+)"

inherit autotools-brokensep pkgconfig gettext github-releases

S = "${UNPACKDIR}/confuse-${PV}"

BBCLASSEXTEND = "native nativesdk"
