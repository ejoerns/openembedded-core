.. SPDX-License-Identifier: CC-BY-SA-2.0-UK

.. _ref-classes-genimage:

``genimage``
============

The :ref:`ref-classes-genimage` class supports generating file system and
disk images using the `genimage <https://github.com/pengutronix/genimage>`__
tool. Its primary purpose is to assemble a complete storage medium image
(SD card, eMMC, NAND, or UBI flash) from a set of pre-built artifacts such
as a kernel, a bootloader, and one or more root filesystem images. Partitions
may each contain a different filesystem type and the overall layout is
controlled by a ``genimage`` configuration file supplied by the recipe.

.. note::

   This class is **not** intended to build a root filesystem itself. It
   must be used in a dedicated disk-image recipe that is separate from any
   recipe that produces a root filesystem. Inheriting both the
   :ref:`ref-classes-image` class and the :ref:`ref-classes-genimage` class
   in the same recipe is a fatal error detected at parse time.

Usage
-----

Create a dedicated recipe that inherits :ref:`ref-classes-genimage` and
provides a ``genimage`` configuration file::

   inherit genimage

   SRC_URI += "file://genimage.config"

The recipe must also declare explicit task dependencies on every artifact
consumed by the ``genimage`` configuration file. For example::

   do_genimage[depends] += " \
       virtual/bootloader:do_deploy \
       core-image-minimal:do_image_complete \
   "

If the recipe requires additional host tools to create the filesystem images
referenced in the ``genimage`` config (such as ``mkfs.ext4``), list them in
:term:`DEPENDS`::

   DEPENDS += "e2fsprogs-native"

The name and location of the produced image follow the same conventions as
standard image recipes and are controlled by
:term:`GENIMAGE_IMAGE_FULLNAME` and :term:`GENIMAGE_IMAGE_LINK_FULLNAME`.
The resulting file is deployed to :term:`DEPLOY_DIR_IMAGE`.

Configuration File
------------------

The ``genimage`` configuration file describes the partition layout and the
filesystem images to embed in each partition.
:term:`BITBAKE_VARIABLE_EXPANSION` is performed on the file's content before
it is passed to ``genimage``, so you can reference BitBake variables
directly. At minimum the configuration should name the output image using
:term:`GENIMAGE_IMAGE_FULLNAME`::

   image ${GENIMAGE_IMAGE_FULLNAME} {
       hdimage {
           align = 1M
           partition-table-type = gpt
       }

       partition boot {
           image = "u-boot.bin"
       }

       partition rootfs {
           image = "${IMAGE_LINK_NAME}.rootfs.ext4"
           partition-type-uuid = "root-arm"
           size = 512M
       }
   }

The default name for the configuration file is ``genimage.config``. This
can be overridden with :term:`GENIMAGE_CONFIG`.

Splitting a Root Filesystem into Multiple Partitions
----------------------------------------------------

The class can unpack an existing root filesystem archive and feed its
directory tree to ``genimage`` as a ``rootpath``. This allows you to split
the rootfs content across multiple partitions based on ``mountpoint``
entries in the ``genimage`` config.

To enable this, set :term:`GENIMAGE_ROOTFS_IMAGE` to the name of a recipe
that produces a root filesystem archive::

   GENIMAGE_ROOTFS_IMAGE = "my-production-image"

The class automatically adds ``my-production-image:do_image_complete`` as
a task dependency. It then unpacks the archive found in
:term:`DEPLOY_DIR_IMAGE` and passes the resulting directory tree to
``genimage`` via ``--rootpath``.

The input archive format defaults to ``tar.bz2``. If your image recipe
produces a different format, set :term:`GENIMAGE_ROOTFS_IMAGE_FSTYPE`
accordingly::

   GENIMAGE_ROOTFS_IMAGE_FSTYPE = "tar.xz"

Since the ``nanbield`` release the image filename includes an
:term:`IMAGE_NAME_SUFFIX` component (set by
:ref:`ref-classes-image-artifact-names`). The class reads this suffix from
:term:`GENIMAGE_ROOTFS_IMAGE_SUFFIX`, which defaults to ``.rootfs``. If
your image recipe uses a different suffix, override it::

   GENIMAGE_ROOTFS_IMAGE_SUFFIX = ""

The partitioning is then controlled in the ``genimage`` config via the
``mountpoint`` keyword::

   image ${GENIMAGE_IMAGE_FULLNAME} {
       hdimage {}

       partition data {
           fs-type = "ext4"
           mountpoint = "/home"
           size = 256M
       }

       partition config {
           fs-type = "ext4"
           mountpoint = "/etc"
           size = 64M
       }

       partition rootfs {
           fs-type = "ext4"
           mountpoint = "/"
           size = 512M
       }
   }

Compression
-----------

The generated image can optionally be compressed after creation. Set
:term:`GENIMAGE_COMPRESSION` to one of the following values:

- ``none`` --- no compression, the raw ``.img`` file is deployed (default).
- ``gzip`` --- compress with ``gzip``; adds a dependency on
  ``pigz-native``.
- ``xz`` --- compress with ``xz``; adds a dependency on ``xz-native``.

Example::

   GENIMAGE_COMPRESSION = "xz"

Block Map (bmap) Generation
----------------------------

Setting :term:`GENIMAGE_CREATE_BMAP` to ``"1"`` causes the class to create
a ``.bmap`` file alongside the image using ``bmaptool``. This file
describes which blocks of the image contain data and enables faster and
safer flashing with ``bmaptool copy``::

   GENIMAGE_CREATE_BMAP = "1"

When enabled, ``bmaptool-native`` is automatically added as a task
dependency.

Variables
---------

The following variables control the behaviour of the
:ref:`ref-classes-genimage` class:

:term:`GENIMAGE_CONFIG`
   Name of the ``genimage`` configuration file to use. BitBake variable
   expansion is applied to its content before it is passed to ``genimage``.
   The file must be provided via :term:`SRC_URI`. Default: ``genimage.config``.

:term:`GENIMAGE_IMAGE_SUFFIX`
   File extension appended to the image name. Default: ``.img``.

:term:`GENIMAGE_IMAGE_FULLNAME`
   Full filename of the produced image, combining :term:`IMAGE_NAME` and
   :term:`GENIMAGE_IMAGE_SUFFIX`. Read-only; derived automatically.

:term:`GENIMAGE_IMAGE_LINK_FULLNAME`
   Filename of the convenience symlink created in :term:`DEPLOY_DIR_IMAGE`,
   combining :term:`IMAGE_LINK_NAME` and :term:`GENIMAGE_IMAGE_SUFFIX`.
   Read-only; derived automatically.

:term:`GENIMAGE_ROOTFS_IMAGE`
   Name of the image recipe whose archive is unpacked and used as the
   ``rootpath`` input to ``genimage``. Leave unset (default) if you do not
   need rootfs splitting.

:term:`GENIMAGE_ROOTFS_IMAGE_FSTYPE`
   Filesystem archive type of the rootfs image identified by
   :term:`GENIMAGE_ROOTFS_IMAGE`. Defaults to the first ``tar``-based entry
   in :term:`IMAGE_FSTYPES`, falling back to ``tar.bz2``.

:term:`GENIMAGE_ROOTFS_IMAGE_SUFFIX`
   :term:`IMAGE_NAME_SUFFIX` value used when constructing the filename of
   the rootfs archive to unpack. Default: ``.rootfs``.

:term:`GENIMAGE_COMPRESSION`
   Compression to apply to the finished image. Allowed values: ``none``
   (default), ``gzip``, ``xz``.

:term:`GENIMAGE_CREATE_BMAP`
   Set to ``"1"`` to generate a ``.bmap`` block-map file alongside the
   image. Default: ``"0"``.

:term:`GENIMAGE_EXTRA_OPTS`
   Additional command-line options forwarded verbatim to the ``genimage``
   invocation. Default: empty.

:term:`GENIMAGE_RUNQEMU`
   Set to ``"1"`` to generate a ``.qemuboot.conf`` alongside the disk
   image so that the recipe can be started with
   :ref:`ref-manual/tasks:running-an-image-under-qemu`. Default: ``"0"``.
   See :ref:`ref-classes-genimage-runqemu` for details.

.. _ref-classes-genimage-runqemu:

Running a genimage Disk Image under QEMU
-----------------------------------------

The :ref:`ref-classes-genimage` class can generate a ``.qemuboot.conf``
file alongside the disk image so that the recipe can be started with
:term:`runqemu` without any manual QEMU flags:

.. code-block:: none

   runqemu <recipe-name> nographic

To enable this, set :term:`GENIMAGE_RUNQEMU` to ``"1"`` in the
disk-image recipe and configure the necessary ``QB_*`` variables.

How it works
~~~~~~~~~~~~

When :term:`GENIMAGE_RUNQEMU` is enabled the class adds a
``do_write_qemuboot_conf`` task (run after ``do_genimage``, before
``do_deploy``) that serialises all ``QB_*`` variables and a small set of
build-path variables into an INI-format ``.qemuboot.conf`` file. Paths
inside the file are stored relative to :term:`DEPLOY_DIR_IMAGE` so the
artifacts remain usable after relocation.

:term:`runqemu` reads this file at boot time. It substitutes the path of
the generated ``.img`` file for the ``@ROOTFS@`` placeholder in
:term:`QB_ROOTFS_OPT` (which for ``qemuarm64`` already wires up a
``virtio-blk-pci`` drive) and passes ``QB_DEFAULT_BIOS`` as the ``-bios``
argument to QEMU.

Supported image types (``img``, ``img.gz``, ``img.xz``) are treated as
fully self-booting disk images by default — QEMU will not load an external
kernel. If you instead want :term:`runqemu` to supply the kernel via
``-kernel`` (e.g. the disk image is a rootfs-only partition image), set::

   QB_FSINFO = "img:no-kernel-in-fs"

Example for qemuarm64
~~~~~~~~~~~~~~~~~~~~~

A genimage disk image for ``qemuarm64`` that contains U-Boot, a kernel,
and a root filesystem typically looks like this::

   inherit genimage

   SRC_URI += "file://genimage.config"

   DEPENDS += "e2fsprogs-native"

   # Pull in all artifacts consumed by genimage.config
   do_genimage[depends] += " \
       virtual/bootloader:do_deploy \
       virtual/kernel:do_deploy \
       core-image-minimal:do_image_complete \
   "

   # Enable runqemu integration
   GENIMAGE_RUNQEMU   = "1"

   # The disk image is self-booting — no external kernel
   QB_DEFAULT_KERNEL  = "none"

   # U-Boot binary deployed to DEPLOY_DIR_IMAGE acts as QEMU firmware.
   # runqemu resolves this relative to DEPLOY_DIR_IMAGE and passes it
   # as: qemu-system-aarch64 ... -bios u-boot.bin
   QB_DEFAULT_BIOS    = "u-boot.bin"

The ``genimage.config`` file for this recipe would embed the kernel and
rootfs in separate GPT partitions, with ``u-boot.bin`` passed to QEMU as
firmware independently of the disk image itself::

   image ${GENIMAGE_IMAGE_FULLNAME} {
       hdimage {
           align = 1M
           partition-table-type = gpt
       }

       partition boot {
           image = "${KERNEL_IMAGETYPE}"
           size  = 64M
       }

       partition rootfs {
           image = "${IMAGE_LINK_NAME}.rootfs.ext4"
           partition-type-uuid = "root-arm"
           size  = 512M
       }
   }

.. note::

   The ``qemuarm64`` machine configuration already defines
   :term:`QB_ROOTFS_OPT` with a ``virtio-blk-pci`` drive and
   :term:`QB_MACHINE` / :term:`QB_CPU` / :term:`QB_SYSTEM_NAME`.
   These values are inherited automatically through the machine
   configuration and written into the ``.qemuboot.conf`` by
   ``do_write_qemuboot_conf`` — you do not need to repeat them in the
   recipe.

runqemu Variables for genimage
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following ``QB_*`` variables are particularly relevant when using the
:ref:`ref-classes-genimage` class with :term:`runqemu`:

:term:`QB_DEFAULT_KERNEL`
   Set to ``"none"`` for self-booting disk images that contain their own
   bootloader and kernel. :term:`runqemu` will not pass ``-kernel`` to
   QEMU.

:term:`QB_DEFAULT_BIOS`
   Name of a firmware binary deployed to :term:`DEPLOY_DIR_IMAGE` (e.g.
   ``u-boot.bin``). :term:`runqemu` resolves this relative to
   :term:`DEPLOY_DIR_IMAGE` and passes it to QEMU as ``-bios``. On
   ``qemuarm64`` with ``-machine virt``, this is required for disk-based
   booting because the ``virt`` machine has no built-in firmware.

:term:`QB_FSINFO`
   Controls whether :term:`runqemu` loads an external kernel for a given
   image type. For ``img`` images the default is self-booting (no external
   kernel). Set ``QB_FSINFO = "img:no-kernel-in-fs"`` if the disk image
   contains only a root filesystem and requires QEMU to provide the kernel
   via ``-kernel``.

:term:`QB_KERNEL_CMDLINE_APPEND`
   Additional kernel command-line parameters. Useful to set the correct
   console device, e.g. ``console=ttyAMA0`` for ``qemuarm64``.

:term:`QB_ROOTFS_OPT`
   Full QEMU ``-drive`` string with the ``@ROOTFS@`` placeholder replaced
   by the image path. Inherited from the machine configuration; override
   only if you need a different bus type (e.g. ``virtio-scsi`` instead of
   ``virtio-blk``).
