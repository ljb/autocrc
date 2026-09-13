import io
import os
from contextlib import redirect_stderr, redirect_stdout
from unittest import TestCase, skipIf
from unittest.mock import patch

from conftest import OTHER_PAYLOAD, PAYLOAD_CRC, TempDirTestCase

from autocrc import cli
from autocrc.core import Summary


class ParseArgsTest(TestCase):
    @staticmethod
    def parse(argv):
        with patch("sys.argv", ["autocrc", *argv]):
            return cli._parse_args()

    def test_defaults_to_the_current_directory(self):
        self.assertEqual([os.curdir], self.parse([]).files)

    def test_accepts_a_single_file(self):
        """Regression test: files used to be declared with nargs='?' and came back as a string."""
        self.assertEqual(["check.sfv"], self.parse(["check.sfv"]).files)

    def test_accepts_several_files(self):
        self.assertEqual(["a.bin", "b.bin", "dir"], self.parse(["a.bin", "b.bin", "dir"]).files)

    def test_flag_defaults(self):
        args = self.parse([])
        self.assertFalse(args.recursive)
        self.assertTrue(args.case)
        self.assertFalse(args.windows_paths)
        self.assertTrue(args.crc)
        self.assertTrue(args.sfv)
        self.assertIsNone(args.directory)
        self.assertFalse(args.follow_symlinks)
        self.assertFalse(args.quiet)
        self.assertFalse(args.verbose)

    def test_flags_can_be_toggled(self):
        args = self.parse(["-r", "-i", "-x", "--no-crc", "--no-sfv", "-L", "-q", "-v", "-C", "/tmp"])
        self.assertTrue(args.recursive)
        self.assertFalse(args.case)
        self.assertTrue(args.windows_paths)
        self.assertFalse(args.crc)
        self.assertFalse(args.sfv)
        self.assertEqual("/tmp", args.directory)
        self.assertTrue(args.follow_symlinks)
        self.assertTrue(args.quiet)
        self.assertTrue(args.verbose)


class SplitPathsTest(TempDirTestCase):
    def test_splits_files_from_directories(self):
        self.write_file("payload.bin")
        os.mkdir(self.path("sub"))

        file_names, dir_names = cli._split_paths([self.path("payload.bin"), self.path("sub")])

        self.assertEqual([self.path("payload.bin")], file_names)
        self.assertEqual([self.path("sub")], dir_names)

    def test_raises_on_paths_that_do_not_exist(self):
        """Regression test: a mistyped path used to be dropped, making a typo look successful."""
        with self.assertRaises(FileNotFoundError) as context:
            cli._split_paths([self.path("nope")])

        self.assertEqual(self.path("nope"), context.exception.filename)

    def test_raises_on_paths_that_are_neither_file_nor_directory(self):
        fifo = self.path("pipe")
        os.mkfifo(fifo)

        with self.assertRaises(OSError) as context:
            cli._split_paths([fifo])

        self.assertEqual("Not a file or directory", context.exception.strerror)


class MainTest(TempDirTestCase):
    def setUp(self):
        super().setUp()
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(self.temp_dir)

    @staticmethod
    def run_main(argv):
        """Runs main() and returns the exit status together with its stdout and stderr."""
        out, err = io.StringIO(), io.StringIO()
        with patch("sys.argv", ["autocrc", *argv]), redirect_stdout(out), redirect_stderr(err):
            with TestCase().assertRaises(SystemExit) as context:
                cli.main()
        return context.exception.code, out.getvalue(), err.getvalue()

    def test_sfv_argument_is_checked(self):
        """Regression test: passing an sfv-file used to be a no-op that printed 'No CRC-sums found'."""
        self.write_file("payload.bin")
        self.write_sfv("check.sfv", [f"payload.bin {PAYLOAD_CRC}"])

        status, output, _ = self.run_main(["check.sfv"])

        self.assertEqual(0, status)
        self.assertIn("payload.bin", output)
        self.assertIn("OK", output)
        self.assertIn("Tested 1 files, Successful 1, Different 0, Missing 0, Read errors 0", output)

    def test_several_files_are_checked(self):
        self.write_file(f"a [{PAYLOAD_CRC}].bin")
        self.write_file(f"b [{PAYLOAD_CRC}].bin")

        status, output, _ = self.run_main([f"a [{PAYLOAD_CRC}].bin", f"b [{PAYLOAD_CRC}].bin"])

        self.assertEqual(0, status)
        self.assertIn("Tested 2 files, Successful 2", output)

    def test_no_crc_sums_found(self):
        self.write_file("payload.bin")
        status, output, _ = self.run_main([])

        self.assertEqual(0, status)
        self.assertIn("No CRC-sums found", output)

    def test_output_format(self):
        self.write_file(f"video [{PAYLOAD_CRC}].mkv")
        _, output, _ = self.run_main([])

        lines = output.splitlines()
        self.assertEqual(f"Current directory: {os.path.realpath(self.temp_dir)}", lines[0])
        # The status is right-aligned in the space left of FILE_NAME_WIDTH
        self.assertEqual(f"video [{PAYLOAD_CRC}].mkv " + "OK".rjust(57), lines[1])
        self.assertEqual("-" * 80, lines[2])
        self.assertEqual("Everything OK", lines[3])

    def test_results_are_printed_while_the_directory_is_still_being_checked(self):
        """
        Regression test: output used to be withheld until the whole directory was done.

        On a directory of video files that is minutes of complete silence, which is
        indistinguishable from a hang. Each file must be reported as it finishes.
        """
        for name in ["a", "b", "c"]:
            self.write_file(f"{name} [{PAYLOAD_CRC}].bin")

        printed_before_each_check = []
        real_crc32 = cli.check_crcs.__globals__["crc32_of_file"]

        def recording_crc32(path, *args, **kwargs):
            printed_before_each_check.append(out.getvalue().count("\n"))
            return real_crc32(path, *args, **kwargs)

        out = io.StringIO()
        with patch("autocrc.core.crc32_of_file", side_effect=recording_crc32):
            with patch("sys.argv", ["autocrc"]), redirect_stdout(out):
                with self.assertRaises(SystemExit):
                    cli.main()

        # The header is out before the first file is hashed, and each file adds a line
        # before the next one starts. Buffering everything would give [0, 0, 0].
        self.assertEqual([1, 2, 3], printed_before_each_check)

    def test_quiet_says_nothing_when_everything_is_ok(self):
        self.write_file(f"ok [{PAYLOAD_CRC}].bin")
        status, output, _ = self.run_main(["-q"])

        self.assertEqual(0, status)
        self.assertEqual("", output)

    def test_quiet_reports_directories_with_problems(self):
        self.write_file(f"ok [{PAYLOAD_CRC}].bin")
        self.write_file(f"bad [{PAYLOAD_CRC}].bin", OTHER_PAYLOAD)

        status, output, _ = self.run_main(["-q"])

        self.assertEqual(1, status)
        self.assertIn("CRC mismatch", output)
        # The successful file in the reported directory is still hidden
        self.assertNotIn(f"ok [{PAYLOAD_CRC}].bin", output)
        self.assertIn("Tested 2 files, Successful 1, Different 1", output)

    def test_quiet_skips_clean_directories_but_keeps_the_total(self):
        for name in ["a", "b", "c"]:
            self.write_file(f"{name}/ok [{PAYLOAD_CRC}].bin")
        self.write_file(f"bad/broken [{PAYLOAD_CRC}].bin", OTHER_PAYLOAD)

        status, output, _ = self.run_main(["-r", "-q", "."])

        self.assertEqual(1, status)
        self.assertEqual(1, output.count("Current directory:"))
        self.assertIn(f"Current directory: {os.path.realpath(self.path('bad'))}", output)
        self.assertIn("  Tested\t 4 files", output)
        self.assertIn("  Successful\t 3 files", output)

    def test_verbose_shows_both_crcs(self):
        self.write_file(f"bad [{PAYLOAD_CRC}].bin", OTHER_PAYLOAD)
        _, output, _ = self.run_main(["-v"])

        self.assertIn(f"98E82DF9 != {PAYLOAD_CRC}", output)
        self.assertNotIn("CRC mismatch", output)

    def test_mismatch_without_verbose(self):
        self.write_file(f"bad [{PAYLOAD_CRC}].bin", OTHER_PAYLOAD)
        _, output, _ = self.run_main([])

        self.assertIn("CRC mismatch", output)

    def test_recursive_prints_a_total_summary(self):
        self.write_file(f"a/one [{PAYLOAD_CRC}].bin")
        self.write_file(f"b/two [{PAYLOAD_CRC}].bin")

        status, output, _ = self.run_main(["-r", "."])

        self.assertEqual(0, status)
        self.assertIn("  Tested\t 2 files", output)
        self.assertIn("  Successful\t 2 files", output)

    def test_directory_header_is_absolute_for_a_relative_argument(self):
        self.write_file(f"sub/video [{PAYLOAD_CRC}].mkv")
        _, output, _ = self.run_main(["sub"])

        self.assertIn(f"Current directory: {os.path.realpath(self.path('sub'))}", output)

    def test_directory_headers_are_consistent_within_a_recursive_run(self):
        """Regression test: the root used to print absolute and its subdirectories relative."""
        self.write_file(f"top [{PAYLOAD_CRC}].bin")
        self.write_file(f"sub/nested [{PAYLOAD_CRC}].bin")

        _, output, _ = self.run_main(["-r", "."])

        headers = [line.removeprefix("Current directory: ") for line in output.splitlines() if "Current" in line]
        self.assertTrue(all(os.path.isabs(header) for header in headers), headers)

    def test_directories_are_reported_in_sorted_order(self):
        for name in ["c", "a", "b"]:
            self.write_file(f"{name}/ok [{PAYLOAD_CRC}].bin")

        _, output, _ = self.run_main(["-r", "."])

        headers = [line.removeprefix("Current directory: ") for line in output.splitlines() if "Current" in line]
        self.assertEqual([os.path.realpath(self.path(name)) for name in ["a", "b", "c"]], headers)

    def test_directory_option_changes_working_directory(self):
        self.write_file(f"sub/video [{PAYLOAD_CRC}].mkv")
        os.chdir("/")

        status, output, _ = self.run_main(["-C", self.path("sub")])

        self.assertEqual(0, status)
        self.assertIn("Tested 1 files, Successful 1", output)

    def test_directory_option_applies_to_relative_arguments(self):
        """Regression test: paths used to be resolved before -C had changed directory."""
        self.write_file(f"target/sub/deep [{PAYLOAD_CRC}].bin")
        os.chdir("/")

        status, output, _ = self.run_main(["-C", self.path("target"), "sub"])

        self.assertEqual(0, status)
        self.assertIn("Tested 1 files, Successful 1", output)

    @skipIf(os.geteuid() == 0, "root bypasses file permissions")
    def test_unreadable_directory_is_reported_and_does_not_stop_the_walk(self):
        """Regression test: os.walk swallowed the error and the run looked complete."""
        self.write_file(f"readable/ok [{PAYLOAD_CRC}].bin")
        locked = self.path("locked")
        os.mkdir(locked)
        os.chmod(locked, 0o000)

        status, output, errors = self.run_main(["-r", "."])

        self.assertIn("Permission denied", errors)
        self.assertIn("locked", errors)
        # The rest of the tree is still checked, but the run does not claim success
        self.assertIn("Tested 1 files, Successful 1", output)
        self.assertEqual(4, status)

    def test_keyboard_interrupt_exits_130(self):
        self.write_file(f"ok [{PAYLOAD_CRC}].bin")

        with patch("autocrc.cli.check_crcs", side_effect=KeyboardInterrupt):
            status, _, _ = self.run_main([])

        self.assertEqual(130, status)

    def test_exit_status(self):
        test_data = [
            ("different", 1),
            ("missing", 2),
            ("different missing", 3),
            ("read_error", 4),
            ("different read_error", 5),
            ("missing read_error", 6),
            ("different missing read_error", 7),
        ]

        for problems, expected in test_data:
            with self.subTest(problems=problems):
                self.assertEqual(expected, cli._exit_status(self._summary_with(problems.split())))

    def test_unreadable_dirs_set_the_read_error_bit(self):
        self.assertEqual(4, cli._exit_status(Summary(nr_files=1), had_unreadable_dirs=True))
        self.assertEqual(5, cli._exit_status(Summary(nr_files=1, nr_different=1), had_unreadable_dirs=True))

    @skipIf(os.geteuid() == 0, "root bypasses file permissions")
    def test_explicitly_named_unreadable_directory_fails_loudly(self):
        """A directory the user named by hand is an error, not something to skip past."""
        locked = self.path("locked")
        os.mkdir(locked)
        os.chmod(locked, 0o000)

        status, _, errors = self.run_main([locked])

        self.assertEqual(8, status)
        self.assertIn("Permission denied", errors)

    def test_missing_file_sets_exit_status(self):
        self.write_sfv("check.sfv", [f"gone.bin {PAYLOAD_CRC}"])
        status, output, _ = self.run_main(["check.sfv"])

        self.assertEqual(2, status)
        self.assertIn("No such file", output)

    def test_nonexistent_path_is_an_error(self):
        """Regression test: this used to print 'No CRC-sums found' and exit 0."""
        status, output, errors = self.run_main([self.path("nope")])

        self.assertEqual(8, status)
        self.assertIn("No such file or directory", errors)
        self.assertIn("nope", errors)
        self.assertNotIn("No CRC-sums found", output)

    @staticmethod
    def _summary_with(problems):
        return Summary(
            nr_files=len(problems),
            nr_different="different" in problems,
            nr_missing="missing" in problems,
            nr_read_errors="read_error" in problems,
        )
