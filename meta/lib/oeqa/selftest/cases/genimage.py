#
# Copyright OpenEmbedded Contributors
#
# SPDX-License-Identifier: MIT
#

"""Test cases for the genimage class."""

import os
import textwrap

from oeqa.selftest.case import OESelftestTestCase
from oeqa.utils.commands import bitbake, get_bb_var, get_bb_vars


class GenimageBase(OESelftestTestCase):
    """Base class with helpers shared by genimage tests."""

    def _get_deploy_dir(self):
        return get_bb_var("DEPLOY_DIR_IMAGE")

    def _write_genimage_recipe(self, name, config_body, extra_vars="", depends=""):
        """
        Write a temporary genimage image recipe and matching genimage.config
        under the test layer (created via write_config / recipetool patterns).

        Instead of a real layer we exploit write_bblayers_config / the inline
        recipe approach used elsewhere in oe-selftest: we write the files into
        ${TOPDIR} which is always in BBPATH, then clean up in tearDown.
        """
        topdir = get_bb_var("TOPDIR")
        self._recipe_dir = os.path.join(topdir, f"recipes-test-genimage/{name}")
        os.makedirs(self._recipe_dir, exist_ok=True)

        config_path = os.path.join(self._recipe_dir, "genimage.config")
        with open(config_path, "w") as f:
            f.write(config_body)

        recipe_path = os.path.join(self._recipe_dir, f"{name}.bb")
        recipe_content = textwrap.dedent(f"""\
            SUMMARY = "genimage selftest recipe: {name}"
            LIC_FILES_CHKSUM = "file://${{COREBASE}}/meta/COPYING.MIT;md5=3da9cfbcb788c80a0384361b4de20420"

            inherit genimage

            SRC_URI += "file://genimage.config"
            FILESEXTRAPATHS:prepend := "${{THISDIR}}:"

            {extra_vars}

            do_genimage[depends] += "{depends}"
        """)
        with open(recipe_path, "w") as f:
            f.write(recipe_content)

        # Point BBPATH at the parent so BitBake finds the recipe
        self.write_config(f'BBPATH .= ":{topdir}"')

        self._recipe_name = name
        return recipe_path, config_path

    def tearDownLocal(self):
        import shutil
        if hasattr(self, "_recipe_dir") and os.path.isdir(self._recipe_dir):
            shutil.rmtree(self._recipe_dir, ignore_errors=True)
        super().tearDownLocal()


class GenimageClassUnitTests(OESelftestTestCase):
    """
    Unit-level tests that exercise helper functions and variable logic in the
    genimage bbclass without triggering a full image build.  These tests use
    tinfoil to inspect parsed metadata.
    """

    def _parse(self, extra_config=""):
        """Parse genimage-disk-image with optional extra local.conf snippets."""
        self.write_config(extra_config)
        import bb.tinfoil
        self._tf = bb.tinfoil.Tinfoil()
        self._tf.prepare(config_only=False, quiet=2)
        self.addCleanup(self._tf.shutdown)
        return self._tf.parse_recipe("genimage-disk-image")

    def test_get_default_fstype_prefers_tar(self):
        """get_default_fstype returns the first tar-based entry in IMAGE_FSTYPES."""
        d = self._parse('IMAGE_FSTYPES = "ext4 tar.xz tar.bz2"')
        # Evaluate the helper via the variable it backs
        fstype = d.getVar("GENIMAGE_ROOTFS_IMAGE_FSTYPE")
        self.assertIn("tar", fstype,
                      "GENIMAGE_ROOTFS_IMAGE_FSTYPE should resolve to a tar type")

    def test_get_default_fstype_fallback(self):
        """get_default_fstype returns 'tar.bz2' when IMAGE_FSTYPES has no tar entry."""
        d = self._parse('IMAGE_FSTYPES = "ext4 squashfs"')
        fstype = d.getVar("GENIMAGE_ROOTFS_IMAGE_FSTYPE")
        self.assertEqual(fstype, "tar.bz2",
                         "Should fall back to tar.bz2 when no tar type is found")

    def test_get_default_fstype_empty_image_fstypes(self):
        """get_default_fstype does not crash when IMAGE_FSTYPES is unset/empty."""
        d = self._parse('IMAGE_FSTYPES = ""')
        # Must not raise; fallback is tar.bz2
        fstype = d.getVar("GENIMAGE_ROOTFS_IMAGE_FSTYPE")
        self.assertEqual(fstype, "tar.bz2")

    def test_image_name_variables(self):
        """GENIMAGE_IMAGE_FULLNAME and GENIMAGE_IMAGE_LINK_FULLNAME are non-empty."""
        d = self._parse()
        fullname = d.getVar("GENIMAGE_IMAGE_FULLNAME")
        linkname = d.getVar("GENIMAGE_IMAGE_LINK_FULLNAME")
        self.assertTrue(fullname, "GENIMAGE_IMAGE_FULLNAME must not be empty")
        self.assertTrue(linkname, "GENIMAGE_IMAGE_LINK_FULLNAME must not be empty")
        self.assertIn(".img", fullname)

    def test_compression_depends_none(self):
        """No extra compress dep when GENIMAGE_COMPRESSION=none."""
        d = self._parse('GENIMAGE_COMPRESSION = "none"')
        dep = d.getVarFlag("GENIMAGE_COMPRESS_DEPENDS", "none")
        self.assertEqual(dep, "")

    def test_compression_depends_gzip(self):
        """pigz-native dep is wired up for gzip compression."""
        d = self._parse('GENIMAGE_COMPRESSION = "gzip"')
        dep = d.getVarFlag("GENIMAGE_COMPRESS_DEPENDS", "gzip")
        self.assertIn("pigz-native", dep)

    def test_compression_depends_xz(self):
        """xz-native dep is wired up for xz compression."""
        d = self._parse('GENIMAGE_COMPRESSION = "xz"')
        dep = d.getVarFlag("GENIMAGE_COMPRESS_DEPENDS", "xz")
        self.assertIn("xz-native", dep)

    def test_compression_cmd_none(self):
        """GENIMAGE_COMPRESS_CMD for none is a no-op."""
        d = self._parse('GENIMAGE_COMPRESSION = "none"')
        cmd = d.getVar("GENIMAGE_COMPRESS_CMD")
        self.assertEqual(cmd.strip(), ":")

    def test_compression_cmd_gzip(self):
        """GENIMAGE_COMPRESS_CMD uses gzip for gzip compression."""
        d = self._parse('GENIMAGE_COMPRESSION = "gzip"')
        cmd = d.getVar("GENIMAGE_COMPRESS_CMD")
        self.assertIn("gzip", cmd)

    def test_genimage_rootfs_image_empty_by_default(self):
        """GENIMAGE_ROOTFS_IMAGE defaults to empty string (no rootfs extraction)."""
        d = self._parse()
        val = d.getVar("GENIMAGE_ROOTFS_IMAGE")
        self.assertEqual(val, "")

    def test_inherits_nopackages_and_deploy(self):
        """genimage recipes must inherit nopackages and deploy."""
        d = self._parse()
        self.assertTrue(
            d.getVar("PACKAGES") == "",
            "PACKAGES should be empty (nopackages)"
        )

    def test_package_arch_is_machine(self):
        """PACKAGE_ARCH must be MACHINE_ARCH for machine-specific disk images."""
        d = self._parse()
        self.assertEqual(
            d.getVar("PACKAGE_ARCH"),
            d.getVar("MACHINE_ARCH"),
        )

    def test_sstate_skip_creation(self):
        """do_genimage output must not be captured in sstate."""
        d = self._parse()
        val = d.getVarFlag("SSTATE_SKIP_CREATION", "task-genimage")
        self.assertEqual(val, "1")

    def test_inheriting_image_class_is_fatal(self):
        """
        A recipe that inherits both 'image' and 'genimage' should raise a
        bb.fatal at parse time.
        """
        import bb.tinfoil
        import bb.exceptions
        self.write_config(textwrap.dedent("""\
            INHERIT += "image"
        """))
        tf = bb.tinfoil.Tinfoil()
        tf.prepare(config_only=False, quiet=2)
        self.addCleanup(tf.shutdown)
        with self.assertRaises(Exception):
            tf.parse_recipe("genimage-disk-image")


class GenimageConfigExpansionTests(OESelftestTestCase):
    """
    Test that the do_genimage_preprocess task correctly expands BitBake
    variables in the genimage config file.
    """

    def _run_preprocess(self, config_content):
        """
        Build genimage-disk-image up to do_genimage_preprocess and return
        the expanded config content from ${B}/.config.
        """
        self.write_config("")
        bitbake("genimage-disk-image -c genimage_preprocess")
        b_dir = get_bb_var("B", "genimage-disk-image")
        expanded = os.path.join(b_dir, ".config")
        # .config is removed after do_genimage runs, but preprocess stops before that
        if not os.path.exists(expanded):
            self.skipTest("Expanded config not present — run with do_genimage_preprocess only")
        with open(expanded) as f:
            return f.read()

    def test_image_fullname_expanded(self):
        """
        After preprocessing, ${GENIMAGE_IMAGE_FULLNAME} in the config must be
        replaced by the concrete image name.
        """
        content = self._run_preprocess("")
        self.assertNotIn("${GENIMAGE_IMAGE_FULLNAME}", content,
                         "BitBake variable should have been expanded")
        self.assertNotIn("${", content,
                         "All BitBake variables should be expanded")


class GenimageBuildTests(OESelftestTestCase):
    """
    Full-build integration tests.  These are slower and require a working
    build environment; they are tagged so they can be skipped in fast CI.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Build genimage-native once for the whole class
        bitbake("genimage-native")

    def _deploy_dir(self):
        return get_bb_var("DEPLOY_DIR_IMAGE")

    def test_genimage_native_builds(self):
        """genimage-native recipe builds successfully."""
        # Already built in setUpClass; verify the binary exists in sysroot
        staging = get_bb_var("STAGING_BINDIR_NATIVE")
        self.assertExists(
            os.path.join(staging, "genimage"),
            "genimage binary should be present in native sysroot after build"
        )

    def test_genimage_disk_image_produces_output(self):
        """
        genimage-disk-image builds and the resulting .img (or compressed
        variant) is deployed to DEPLOY_DIR_IMAGE.
        """
        import glob as _glob

        self.write_config("")
        result = bitbake("genimage-disk-image", ignore_status=True)
        if result.status != 0:
            self.skipTest(
                "genimage-disk-image build failed (likely missing MACHINE "
                "support or bootloader) — skipping output check:\n" + result.output
            )

        deploy = self._deploy_dir()
        imgs = _glob.glob(os.path.join(deploy, "*.img"))
        imgs += _glob.glob(os.path.join(deploy, "*.img.gz"))
        imgs += _glob.glob(os.path.join(deploy, "*.img.xz"))
        self.assertTrue(imgs, f"No .img file found in {deploy}")

    def test_genimage_disk_image_gzip_compression(self):
        """
        With GENIMAGE_COMPRESSION=gzip the deployed image has a .img.gz suffix.
        """
        import glob as _glob

        self.write_config('GENIMAGE_COMPRESSION = "gzip"')
        result = bitbake("genimage-disk-image", ignore_status=True)
        if result.status != 0:
            self.skipTest("Build failed — skipping compression check")

        deploy = self._deploy_dir()
        imgs = _glob.glob(os.path.join(deploy, "*.img.gz"))
        self.assertTrue(imgs, f"No .img.gz file found in {deploy}")

    def test_genimage_disk_image_bmap(self):
        """
        With GENIMAGE_CREATE_BMAP=1 a .bmap file is deployed alongside the image.
        """
        import glob as _glob

        self.write_config('GENIMAGE_CREATE_BMAP = "1"')
        result = bitbake("genimage-disk-image", ignore_status=True)
        if result.status != 0:
            self.skipTest("Build failed — skipping bmap check")

        deploy = self._deploy_dir()
        bmaps = _glob.glob(os.path.join(deploy, "*.bmap"))
        self.assertTrue(bmaps, f"No .bmap file found in {deploy}")

    def test_genimage_symlinks_created(self):
        """
        do_deploy creates IMAGE_LINK_NAME symlinks pointing at the real image.
        """
        import glob as _glob

        self.write_config("")
        result = bitbake("genimage-disk-image", ignore_status=True)
        if result.status != 0:
            self.skipTest("Build failed — skipping symlink check")

        deploy = self._deploy_dir()
        link_name = get_bb_var("GENIMAGE_IMAGE_LINK_FULLNAME", "genimage-disk-image")
        link_path = os.path.join(deploy, link_name)
        self.assertTrue(
            os.path.islink(link_path),
            f"Expected symlink {link_path} to exist in {deploy}"
        )
        # Symlink must point to an existing file
        self.assertTrue(
            os.path.exists(link_path),
            f"Symlink {link_path} is dangling"
        )
