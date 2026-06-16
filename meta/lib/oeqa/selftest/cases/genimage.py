#
# Copyright OpenEmbedded Contributors
#
# SPDX-License-Identifier: MIT
#

"""Test cases for genimage."""

import os

from glob import glob

from oeqa.selftest.case import OESelftestTestCase
from oeqa.utils.commands import bitbake, get_bb_var, get_bb_vars, runCmd


class GenimageTestCase(OESelftestTestCase):
    """Shared fixture: prepares parted-native once per process."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Prepare parted host tool once for all tests in this process.
        bitbake('parted-native -c addto_recipe_sysroot')


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

        # Use machine-parseable output (-m) with LC_ALL=C to avoid locale-
        # dependent number formatting (e.g. "1,00MiB" vs "1.00MiB").
        res = runCmd(
            "LC_ALL=C parted -m %s unit MiB p" % images[0],
            native_sysroot=native_sysroot,
        )
        # -m output: line 0 = "BYT;", line 1 = disk info, line 2+ = partitions.
        # Parse the single partition line rather than string-matching it wholesale
        # so the test is resilient to minor parted version differences in field order.
        partition_lines = res.output.splitlines()[2:]
        self.assertEqual(1, len(partition_lines),
                         "Expected exactly one partition, got: %s" % partition_lines)
        fields = partition_lines[0].rstrip(';').split(':')
        # fields: num, start, end, size, fstype, name, flags
        part_num  = fields[0]
        part_size = fields[3]
        part_fs   = fields[4]
        part_name = fields[5]
        self.assertEqual(part_num, "1")
        self.assertEqual(part_fs, "ext4")
        self.assertEqual(part_name, "rootfs")
        # Size should be 256 MiB (allow ±1 MiB for alignment rounding)
        size_mib = float(part_size.replace('MiB', ''))
        self.assertGreater(size_mib, 255, "Partition smaller than expected: %s" % part_size)
        self.assertLess(size_mib, 257,    "Partition larger than expected: %s" % part_size)

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
        bb_vars = get_bb_vars(['DEPLOY_DIR_IMAGE', 'MACHINE'], 'genimage-selftest-image')
        deploy_dir = bb_vars['DEPLOY_DIR_IMAGE']
        machine = bb_vars['MACHINE']
        # expect exactly one (non-symlinked) *.img
        images = glob(os.path.join(deploy_dir, "genimage-selftest-image-%s-*.img" % machine))
        self.assertEqual(1, len(images))
        self.assertTrue(os.path.exists(os.path.join(deploy_dir, "rootfs.ext4")))
        self.assertTrue(os.path.exists(os.path.join(deploy_dir, "home.ext4")))
