#
# Copyright OpenEmbedded Contributors
#
# SPDX-License-Identifier: MIT
#

"""Test cases for genimage."""

import json
import os
import shutil
import subprocess
import tempfile

from glob import glob

from oeqa.selftest.case import OESelftestTestCase
from oeqa.utils.commands import bitbake, get_bb_var, get_bb_vars, runCmd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sfdisk_partitions(image_path):
    """Return the 'partitions' list from sfdisk --json output."""
    result = runCmd("sfdisk --json %s" % image_path)
    data = json.loads(result.output)
    return data["partitiontable"]["partitions"]


def _sfdisk_label(image_path):
    """Return the partition-table label string ('gpt', 'dos', ...)."""
    result = runCmd("sfdisk --json %s" % image_path)
    data = json.loads(result.output)
    return data["partitiontable"]["label"]


def _sector_bytes(image_path):
    """Return the logical sector size in bytes reported by sfdisk."""
    result = runCmd("sfdisk --json %s" % image_path)
    data = json.loads(result.output)
    return int(data["partitiontable"].get("sectorsize", 512))


# ---------------------------------------------------------------------------
# Base class — builds core-image-minimal once
# ---------------------------------------------------------------------------

class GenimageTestCase(OESelftestTestCase):
    """Shared fixture: ensures core-image-minimal with ext4 is built once."""

    _base_ready = False

    def setUpLocal(self):
        super().setUpLocal()

        if not GenimageTestCase._base_ready:
            # Build core-image-minimal with both ext4 (consumed by the
            # partition-image tests) and tar.bz2 (consumed by the
            # rootfs-split tests via GENIMAGE_ROOTFS_IMAGE).
            bitbake('parted-native -c addto_recipe_sysroot')
            GenimageTestCase._base_ready = True

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def _deploy_dir(self):
        return get_bb_var("DEPLOY_DIR_IMAGE")

    def _deployed(self, suffix):
        """Return list of files in DEPLOY_DIR_IMAGE ending in *suffix*."""
        return glob(os.path.join(self._deploy_dir(), "*" + suffix))

    def _link_name_img(self):
        """Full path of the IMAGE_LINK_NAME symlink for the .img file."""
        bb_vars = get_bb_vars(
            ["DEPLOY_DIR_IMAGE", "IMAGE_LINK_NAME", "GENIMAGE_IMAGE_SUFFIX"],
            self.IMAGE,
        )
        suffix = bb_vars["GENIMAGE_IMAGE_SUFFIX"] or ".img"
        return os.path.join(
            bb_vars["DEPLOY_DIR_IMAGE"],
            bb_vars["IMAGE_LINK_NAME"] + suffix,
        )


class GenimageRecipeTests(GenimageTestCase):
    """Build genimage-selftest-image with various settings and check output."""

    def test_basic_image(self):
        """Built image is copied to DEPLOY_DIR_IMAGE."""
        self.append_config('IMAGE_FSTYPES:append = " ext4"')
        bitbake("genimage-selftest-image")
        bb_vars = get_bb_vars(['DEPLOY_DIR_IMAGE', 'MACHINE'], 'genimage-selftest-image')
        deploy_dir = bb_vars['DEPLOY_DIR_IMAGE']
        machine = bb_vars['MACHINE']
        # expect exactly one (non-symlinked) *.img
        images = glob(os.path.join(deploy_dir, "genimage-selftest-image-%s-*.img" % machine))
        self.assertEqual(1, len(images))

        native_sysroot = get_bb_var("RECIPE_SYSROOT_NATIVE", "parted-native")

        # verify partition size with parted
        res = runCmd("parted -m %s unit mib p" % images[0],
                     native_sysroot=native_sysroot, stderr=subprocess.PIPE)

        self.assertEqual(res.output.splitlines()[2:], [
                        "1:1.00MiB:257MiB:256MiB:ext4:rootfs:;"
                        ])
	
    def test_compression(self):
        """Tests that GENIMAGE_COMPRESSION=gzip produces a .img.gz file."""
        self.write_recipeinc(
            'images',
            'GENIMAGE_COMPRESSION:pn-genimage-selftest-image = "gzip"\n',
        )
        self.append_config('IMAGE_FSTYPES:append = " ext4"')
        bitbake("genimage-selftest-image")
        bb_vars = get_bb_vars(['DEPLOY_DIR_IMAGE', 'MACHINE'], 'genimage-selftest-image')
        deploy_dir = bb_vars['DEPLOY_DIR_IMAGE']
        machine = bb_vars['MACHINE']
        # expect exactly one (non-symlinked) *.img.gz
        compressed = glob(os.path.join(deploy_dir, "genimage-selftest-image-%s-*.img.gz" % machine))
        self.assertEqual(1, len(compressed))
        # The uncompressed .img must not remain
        uncompressed = glob(os.path.join(deploy_dir, "genimage-selftest-image-%s-*.img" % machine))
        self.assertEqual(0, len(uncompressed))

    def test_bmap(self):
        """Tests that GENIMAGE_CREATE_BMAP=1 produces a .img.bmap file alongside the image."""
        self.append_config('IMAGE_FSTYPES:append = " ext4"')
        self.write_recipeinc(
            'images',
            'GENIMAGE_CREATE_BMAP:pn-genimage-selftest-image = "1"\n',
        )
        bitbake("genimage-selftest-image")
        bb_vars = get_bb_vars(['DEPLOY_DIR_IMAGE', 'MACHINE'], 'genimage-selftest-image')
        deploy_dir = bb_vars['DEPLOY_DIR_IMAGE']
        machine = bb_vars['MACHINE']
        # expect exactly one (non-symlinked) *.img
        images = glob(os.path.join(deploy_dir, "genimage-selftest-image-%s-*.img" % machine))
        self.assertEqual(1, len(images))
        # expect exactly one corresponding (non-symlinked) *.img.bmap
        bmaps = glob(os.path.join(deploy_dir, "genimage-selftest-image-%s-*.img.bmap" % machine))
        self.assertEqual(1, len(bmaps))

    def test_rootfs_split(self):
        """Tests the rootfs-splitting feature via GENIMAGE_ROOTFS_IMAGE."""
        self.append_config('IMAGE_FSTYPES:append = " tar.bz2"')
        self.write_recipeinc(
            'images',
            'GENIMAGE_ROOTFS_IMAGE:pn-genimage-selftest-image = "core-image-minimal"\n'
            'GENIMAGE_CONFIG_NAME:pn-genimage-selftest-image = "genimage-rootfs-split.config"\n'
        )
        bitbake("genimage-selftest-image")
        bitbake("genimage-selftest-image")
        bb_vars = get_bb_vars(['DEPLOY_DIR_IMAGE', 'MACHINE'], 'genimage-selftest-image')
        deploy_dir = bb_vars['DEPLOY_DIR_IMAGE']
        machine = bb_vars['MACHINE']
        # expect exactly one (non-symlinked) *.img
        images = glob(os.path.join(deploy_dir, "genimage-selftest-image-%s-*.img" % machine))
        self.assertEqual(1, len(images))
        assert os.path.exists(os.path.join(deploy_dir, "rootfs.ext4"))
        assert os.path.exists(os.path.join(deploy_dir, "home.ext4"))


# ---------------------------------------------------------------------------
# Rootfs-split tests (GENIMAGE_ROOTFS_IMAGE)
# ---------------------------------------------------------------------------

class GenimageRootfsSplitTests(GenimageTestCase):
    """Tests for the rootfs-splitting feature via GENIMAGE_ROOTFS_IMAGE.

    When GENIMAGE_ROOTFS_IMAGE is set, the class unpacks the named recipe's
    tar archive and passes the resulting directory tree to genimage as
    --rootpath.  genimage can then assign different subtrees to separate
    partitions using the 'mountpoint' keyword in the config.

    The fixture uses genimage-rootfs-split.config which creates two
    partitions: 'rootfs' (mountpoint='/') and 'home' (mountpoint='/home').
    """

    # Standard recipeinc snippet applied by every test in this class
    _ROOTFS_SPLIT_INC = (
        'GENIMAGE_ROOTFS_IMAGE:pn-genimage-selftest-image = "core-image-minimal"\n'
        'GENIMAGE_ROOTFS_IMAGE_FSTYPE:pn-genimage-selftest-image = "tar.bz2"\n'
        'GENIMAGE_CONFIG_NAME:pn-genimage-selftest-image = "genimage-rootfs-split.config"\n'
    )

    def setUpLocal(self):
        super().setUpLocal()
        self.write_recipeinc("images", self._ROOTFS_SPLIT_INC)

    # -- helpers ------------------------------------------------------------

    def _build(self):
        bitbake(self.IMAGE)

    def _extract_partition(self, image_path, index, out_path):
        """Copy one partition out of *image_path* into *out_path* using dd."""
        parts = _sfdisk_partitions(image_path)
        sector_size = _sector_bytes(image_path)
        p = parts[index]
        runCmd(
            "dd if=%s of=%s bs=%d skip=%d count=%d status=none"
            % (image_path, out_path, sector_size, p["start"], p["size"])
        )

    # -- build / output -----------------------------------------------------

    def test_rootfs_split_build_succeeds(self):
        """Build completes when GENIMAGE_ROOTFS_IMAGE is set."""
        result = bitbake(self.IMAGE, ignore_status=True)
        self.assertEqual(
            result.status, 0,
            "Build failed with GENIMAGE_ROOTFS_IMAGE set:\n%s" % result.output,
        )

    def test_rootfs_split_image_deployed(self):
        """Output image is deployed to DEPLOY_DIR_IMAGE."""
        self._build()
        imgs = self._deployed(".img")
        self.assertEqual(
            len(imgs), 1,
            "Expected exactly one .img, got: %s" % imgs,
        )

    # -- partition structure ------------------------------------------------

    def test_rootfs_split_partition_count(self):
        """Split config produces exactly two partitions (rootfs + home)."""
        self._build()
        imgs = self._deployed(".img")
        self.assertEqual(len(imgs), 1)
        parts = _sfdisk_partitions(imgs[0])
        self.assertEqual(
            len(parts), 2,
            "Expected 2 partitions, got %d: %s" % (len(parts), parts),
        )

    def test_rootfs_split_partition_table_is_gpt(self):
        """Split image uses GPT."""
        self._build()
        imgs = self._deployed(".img")
        self.assertEqual(len(imgs), 1)
        self.assertEqual(_sfdisk_label(imgs[0]), "gpt")

    def test_rootfs_split_partition_sizes(self):
        """Partition sizes match the config: ~200 MiB rootfs, ~32 MiB home."""
        self._build()
        imgs = self._deployed(".img")
        self.assertEqual(len(imgs), 1)
        parts = _sfdisk_partitions(imgs[0])
        sector_size = _sector_bytes(imgs[0])

        rootfs_mib = parts[0]["size"] * sector_size / (1024 * 1024)
        home_mib   = parts[1]["size"] * sector_size / (1024 * 1024)

        self.assertGreater(rootfs_mib, 195, "rootfs partition too small: %.1f MiB" % rootfs_mib)
        self.assertLess(rootfs_mib, 205,    "rootfs partition too large: %.1f MiB" % rootfs_mib)
        self.assertGreater(home_mib, 27,    "home partition too small: %.1f MiB" % home_mib)
        self.assertLess(home_mib, 37,       "home partition too large: %.1f MiB" % home_mib)

    # -- content verification -----------------------------------------------

    def test_rootfs_partition_contains_rootfs_content(self):
        """The rootfs partition (mountpoint='/') contains typical root directories.

        Verifies that the tar archive was actually unpacked and fed to genimage
        as --rootpath: the output ext4 partition must hold the root filesystem
        tree (e.g. /etc, /bin).  Inspection is done with debugfs.
        """
        if not shutil.which("debugfs"):
            self.skipTest("debugfs not available on this host")

        self._build()
        imgs = self._deployed(".img")
        self.assertEqual(len(imgs), 1)

        with tempfile.NamedTemporaryFile(suffix=".ext4", delete=False) as f:
            part_path = f.name
        try:
            self._extract_partition(imgs[0], 0, part_path)
            result = runCmd(
                "debugfs -R 'ls -p /' %s 2>/dev/null" % part_path,
                ignore_status=True,
            )
            entries = result.output
            self.assertIn(
                "etc", entries,
                "/etc not found in rootfs partition — rootfs may not have been "
                "unpacked via GENIMAGE_ROOTFS_IMAGE",
            )
            self.assertIn(
                "bin", entries,
                "/bin not found in rootfs partition",
            )
        finally:
            os.unlink(part_path)

    def test_home_partition_is_separate_filesystem(self):
        """The home partition is a valid ext4 filesystem (not empty/zeroed).

        genimage creates this filesystem from the /home subtree of the
        unpacked rootfs.  Even though core-image-minimal has an empty /home,
        the partition must contain a valid ext4 superblock.
        """
        if not shutil.which("debugfs"):
            self.skipTest("debugfs not available on this host")

        self._build()
        imgs = self._deployed(".img")
        self.assertEqual(len(imgs), 1)

        with tempfile.NamedTemporaryFile(suffix=".ext4", delete=False) as f:
            part_path = f.name
        try:
            self._extract_partition(imgs[0], 1, part_path)
            # 'debugfs -R stat </>'' reads the inode of '/' — succeeds only
            # on a valid ext4 image, fails on a zero-filled block device.
            result = runCmd(
                "debugfs -R 'stat <2>' %s 2>/dev/null" % part_path,
                ignore_status=True,
            )
            self.assertEqual(
                result.status, 0,
                "home partition does not contain a valid ext4 filesystem",
            )
        finally:
            os.unlink(part_path)

    # -- fstype selection ---------------------------------------------------

    def test_rootfs_split_explicit_fstype(self):
        """GENIMAGE_ROOTFS_IMAGE_FSTYPE selects the correct archive format.

        tar.bz2 is set explicitly in _ROOTFS_SPLIT_INC; the build must find
        and unpack the core-image-minimal-<MACHINE>.rootfs.tar.bz2 archive.
        A build success is sufficient evidence that the correct file was used
        (a wrong extension would cause tar to fail at unpack time).
        """
        result = bitbake(self.IMAGE, ignore_status=True)
        self.assertEqual(
            result.status, 0,
            "Build failed with GENIMAGE_ROOTFS_IMAGE_FSTYPE=tar.bz2:\n%s"
            % result.output,
        )
