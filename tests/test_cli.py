import io
import os
from contextlib import redirect_stdout
from unittest import TestCase
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
        self.assertFalse(args.exchange)
        self.assertTrue(args.crc)
        self.assertTrue(args.sfv)
        self.assertIsNone(args.directory)
        self.assertFalse(args.follow)
        self.assertFalse(args.quiet)
        self.assertFalse(args.verbose)

    def test_flags_can_be_toggled(self):
        args = self.parse(["-r", "-i", "-x", "-c", "-s", "-L", "-q", "-v", "-C", "/tmp"])
        self.assertTrue(args.recursive)
        self.assertFalse(args.case)
        self.assertTrue(args.exchange)
        self.assertFalse(args.crc)
        self.assertFalse(args.sfv)
        self.assertEqual("/tmp", args.directory)
        self.assertTrue(args.follow)
        self.assertTrue(args.quiet)
        self.assertTrue(args.verbose)


class SplitPathsTest(TempDirTestCase):
    def test_splits_files_from_directories(self):
        self.write_file("payload.bin")
        os.mkdir(self.path("sub"))

        file_names, dir_names = cli._split_paths([self.path("payload.bin"), self.path("sub")])

        self.assertEqual([self.path("payload.bin")], file_names)
        self.assertEqual([self.path("sub")], dir_names)

    def test_ignores_paths_that_do_not_exist(self):
        self.assertEqual(([], []), cli._split_paths([self.path("nope")]))


class MainTest(TempDirTestCase):
    def setUp(self):
        super().setUp()
        cwd = os.getcwd()
        self.addCleanup(os.chdir, cwd)
        os.chdir(self.temp_dir)

    @staticmethod
    def run_main(argv):
        """Runs main() and returns the exit status together with everything it printed."""
        out = io.StringIO()
        with patch("sys.argv", ["autocrc", *argv]), redirect_stdout(out):
            with TestCase().assertRaises(SystemExit) as context:
                cli.main()
        return context.exception.code, out.getvalue()

    def test_sfv_argument_is_checked(self):
        """Regression test: passing an sfv-file used to be a no-op that printed 'No CRC-sums found'."""
        self.write_file("payload.bin")
        self.write_sfv("check.sfv", [f"payload.bin {PAYLOAD_CRC}"])

        status, output = self.run_main(["check.sfv"])

        self.assertEqual(0, status)
        self.assertIn("payload.bin", output)
        self.assertIn("OK", output)
        self.assertIn("Tested 1 files, Successful 1, Different 0, Missing 0, Read errors 0", output)

    def test_several_files_are_checked(self):
        self.write_file(f"a [{PAYLOAD_CRC}].bin")
        self.write_file(f"b [{PAYLOAD_CRC}].bin")

        status, output = self.run_main([f"a [{PAYLOAD_CRC}].bin", f"b [{PAYLOAD_CRC}].bin"])

        self.assertEqual(0, status)
        self.assertIn("Tested 2 files, Successful 2", output)

    def test_no_crc_sums_found(self):
        self.write_file("payload.bin")
        status, output = self.run_main([])

        self.assertEqual(0, status)
        self.assertIn("No CRC-sums found", output)

    def test_output_format(self):
        self.write_file(f"video [{PAYLOAD_CRC}].mkv")
        _, output = self.run_main([])

        lines = output.splitlines()
        self.assertEqual(f"Current directory: {os.path.realpath(self.temp_dir)}", lines[0])
        # The status is right-aligned in the space left of FILE_NAME_WIDTH
        self.assertEqual(f"video [{PAYLOAD_CRC}].mkv " + "OK".rjust(57), lines[1])
        self.assertEqual("-" * 80, lines[2])
        self.assertEqual("Everything OK", lines[3])

    def test_quiet_says_nothing_when_everything_is_ok(self):
        self.write_file(f"ok [{PAYLOAD_CRC}].bin")
        status, output = self.run_main(["-q"])

        self.assertEqual(0, status)
        self.assertEqual("", output)

    def test_quiet_reports_directories_with_problems(self):
        self.write_file(f"ok [{PAYLOAD_CRC}].bin")
        self.write_file(f"bad [{PAYLOAD_CRC}].bin", OTHER_PAYLOAD)

        status, output = self.run_main(["-q"])

        self.assertEqual(1, status)
        self.assertIn("CRC mismatch", output)
        # The successful file in the reported directory is still hidden
        self.assertNotIn(f"ok [{PAYLOAD_CRC}].bin", output)
        self.assertIn("Tested 2 files, Successful 1, Different 1", output)

    def test_quiet_skips_clean_directories_but_keeps_the_total(self):
        for name in ["a", "b", "c"]:
            self.write_file(f"{name}/ok [{PAYLOAD_CRC}].bin")
        self.write_file(f"bad/broken [{PAYLOAD_CRC}].bin", OTHER_PAYLOAD)

        status, output = self.run_main(["-r", "-q", "."])

        self.assertEqual(1, status)
        self.assertEqual(1, output.count("Current directory:"))
        self.assertIn(f"Current directory: {os.path.realpath(self.path('bad'))}", output)
        self.assertIn("  Tested\t 4 files", output)
        self.assertIn("  Successful\t 3 files", output)

    def test_verbose_shows_both_crcs(self):
        self.write_file(f"bad [{PAYLOAD_CRC}].bin", OTHER_PAYLOAD)
        _, output = self.run_main(["-v"])

        self.assertIn(f"98E82DF9 != {PAYLOAD_CRC}", output)
        self.assertNotIn("CRC mismatch", output)

    def test_mismatch_without_verbose(self):
        self.write_file(f"bad [{PAYLOAD_CRC}].bin", OTHER_PAYLOAD)
        _, output = self.run_main([])

        self.assertIn("CRC mismatch", output)

    def test_recursive_prints_a_total_summary(self):
        self.write_file(f"a/one [{PAYLOAD_CRC}].bin")
        self.write_file(f"b/two [{PAYLOAD_CRC}].bin")

        status, output = self.run_main(["-r", "."])

        self.assertEqual(0, status)
        self.assertIn("  Tested\t 2 files", output)
        self.assertIn("  Successful\t 2 files", output)

    def test_directory_header_is_absolute_for_a_relative_argument(self):
        self.write_file(f"sub/video [{PAYLOAD_CRC}].mkv")
        _, output = self.run_main(["sub"])

        self.assertIn(f"Current directory: {os.path.realpath(self.path('sub'))}", output)

    def test_directory_headers_are_consistent_within_a_recursive_run(self):
        """Regression test: the root used to print absolute and its subdirectories relative."""
        self.write_file(f"top [{PAYLOAD_CRC}].bin")
        self.write_file(f"sub/nested [{PAYLOAD_CRC}].bin")

        _, output = self.run_main(["-r", "."])

        headers = [line.removeprefix("Current directory: ") for line in output.splitlines() if "Current" in line]
        self.assertTrue(all(os.path.isabs(header) for header in headers), headers)

    def test_directories_are_reported_in_sorted_order(self):
        for name in ["c", "a", "b"]:
            self.write_file(f"{name}/ok [{PAYLOAD_CRC}].bin")

        _, output = self.run_main(["-r", "."])

        headers = [line.removeprefix("Current directory: ") for line in output.splitlines() if "Current" in line]
        self.assertEqual([os.path.realpath(self.path(name)) for name in ["a", "b", "c"]], headers)

    def test_directory_option_changes_working_directory(self):
        self.write_file(f"sub/video [{PAYLOAD_CRC}].mkv")
        os.chdir("/")

        status, output = self.run_main(["-C", self.path("sub")])

        self.assertEqual(0, status)
        self.assertIn("Tested 1 files, Successful 1", output)

    def test_directory_option_applies_to_relative_arguments(self):
        """Regression test: paths used to be resolved before -C had changed directory."""
        self.write_file(f"target/sub/deep [{PAYLOAD_CRC}].bin")
        os.chdir("/")

        status, output = self.run_main(["-C", self.path("target"), "sub"])

        self.assertEqual(0, status)
        self.assertIn("Tested 1 files, Successful 1", output)

    def test_keyboard_interrupt_exits_130(self):
        self.write_file(f"ok [{PAYLOAD_CRC}].bin")

        with patch("autocrc.cli.check_dir", side_effect=KeyboardInterrupt):
            status, _ = self.run_main([])

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

    def test_missing_file_sets_exit_status(self):
        self.write_sfv("check.sfv", [f"gone.bin {PAYLOAD_CRC}"])
        status, output = self.run_main(["check.sfv"])

        self.assertEqual(2, status)
        self.assertIn("No such file", output)

    def test_nonexistent_path_is_ignored(self):
        status, output = self.run_main([self.path("nope")])

        self.assertEqual(0, status)
        self.assertIn("No CRC-sums found", output)

    @staticmethod
    def _summary_with(problems):
        return Summary(
            nr_files=len(problems),
            nr_different="different" in problems,
            nr_missing="missing" in problems,
            nr_read_errors="read_error" in problems,
        )
