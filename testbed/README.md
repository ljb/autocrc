# autocrc testbed

Scenarios for exercising the **installed** `autocrc` end to end, by hand before a
release and as the `end-to-end` job in CI.

The pytest suite calls `cli.main()` in-process with a patched `sys.argv`. This
does not: it runs the console script against real files, with real permission
bits, real symlinks and a real fifo, and checks the exit status a shell sees.
That also makes it a check on the packaging -- if the entry point breaks, this
notices. Rebuild at any time with `./build.py`,
remove the generated files with `./build.py --clean`, or take one pass over
everything with `./run-scenarios.sh`. Nothing it generates is tracked by git.

`run-scenarios.sh` compares the exit status of every scenario against what this
file claims and fails if they disagree, so the expectations written down here
cannot quietly drift away from what autocrc actually does.

Every sum that is meant to match was computed from the real file contents, so a
line marked OK below really is OK. Files that are meant to fail carry the
deliberately wrong sum `DEADBEEF`. Names are prefixed so the intent is visible in
the output itself: `ok-` should pass, `BAD-` should not, `MISSING-` does not
exist, `ignored-` should never be mentioned at all.

Exit status is a bitmask: `1` mismatch, `2` missing, `4` read error, `8` bad
argument, `130` interrupted.

---

## 01-filename-crcs — the three delimiters

```
cd scenarios/01-filename-crcs && autocrc
```

`[XXXXXXXX]`, `(XXXXXXXX)` and `_XXXXXXXX_` are all recognised, and lowercase hex
matches too. The three `ignored-` files are never mentioned: seven hex digits is
too short, `ZZZZZZZZ` is not hex, and one has no sum at all.

Expect 5 tested, 4 successful, 1 different, **exit 1**.

## 02-sfv-basic — sfv parsing

```
cd scenarios/02-sfv-basic && autocrc
```

Comment lines starting with `;` are skipped. A file listed in the sfv but never
created is reported as `No such file` rather than ignored. Paths with a
subdirectory work without any flag.

Expect 4 tested, 2 successful, 1 different, 1 missing, **exit 3**.

## 03-sfv-windows-paths — `-x` / `--windows-paths`

```
cd scenarios/03-sfv-windows-paths && autocrc        # No such file, exit 2
cd scenarios/03-sfv-windows-paths && autocrc -x     # OK, exit 0
```

The sfv uses `Season 1\episode.bin` with a backslash and CRLF line endings, as
produced on Windows. Without `-x` the backslash is part of the file name and
nothing is found.

## 04-sfv-ignore-case — `-i` / `--ignore-case`

```
cd scenarios/04-sfv-ignore-case && autocrc          # 2 missing, exit 2
cd scenarios/04-sfv-ignore-case && autocrc -i       # both OK, exit 0
```

The sfv names `mixedcase.BIN` and `subdir/nested.BIN`; on disk they are
`MixedCase.bin` and `SubDir/Nested.bin`. The second one is the interesting case:
matching is done per path component, so a directory whose case differs is
resolved too. Note that the output prints the real names, not the sfv's.

## 05-permissions — read errors

```
cd scenarios/05-permissions && autocrc              # 1 read error, exit 4
cd scenarios/05-permissions && autocrc -r .         # also complains about locked-dir
```

`ok-read-only` is mode 444: readable, not writable, and checked fine. Before
2.0.0 that was reported as a read error, because files were opened `r+`.

`BAD-unreadable` is mode 000 and is a genuine `Read error`.

`locked-dir` is mode 000, so a recursive run cannot list it. It is reported on
**stderr** and the walk carries on, but the read-error bit is set so the run does
not claim success:

```
autocrc: ./locked-dir: Permission denied
```

Run as root and the permission scenarios stop meaning anything.

## 06-empty-and-missing — zero-byte files

```
cd scenarios/06-empty-and-missing && autocrc
```

An empty file hashes to `00000000`, which is correct and not a special case.
Before 2.0.0 this crashed with `ValueError: cannot mmap an empty file`.

Expect 4 tested, 1 successful, 1 different, 2 missing, **exit 3**.

## 07-symlinks

```
cd scenarios/07-symlinks && autocrc                  # 1 file: ok-link
cd scenarios/07-symlinks && autocrc -r .             # 2 directories
cd scenarios/07-symlinks && autocrc -r linked-subdir # the link as the walk root
```

`ok-link` carries the CRC on the link's own name and points at `target.bin`.
Links to *files* are followed, so it is checked.

`skipped-broken-link` has a valid-looking CRC in its name but dangles. autocrc
says **nothing at all** about it -- a broken link fails the `isfile` check and
never becomes a candidate, so it is not even counted as missing. Worth knowing:
a dead link in a media directory is invisible to a CRC pass.

`linked-subdir` points at `real-subdir`. A recursive walk does **not** descend
into it, so `real-subdir` is visited once and its file counted once. Naming the
link explicitly still works, because it is then the root of the walk rather than
something discovered inside one.

Before 2.0.0 there was a `-L/--follow-symlinks` flag for descending into linked
directories. It was removed: a directory reachable by two paths was checked and
counted twice, which makes the summary wrong, and a link pointing at its own
ancestor made autocrc re-read the same files up to 41 times before the kernel's
symlink limit stopped it.

## 08-recursive — traversal order

```
cd scenarios/08-recursive && autocrc -r .
```

Directories are reported in sorted order — the top, then `alpha`, `bravo`,
`charlie` — regardless of the order the filesystem returns them. `no-crcs-here`
contains a file without a sum and is never mentioned, which is why the total
summary counts four directories' worth of files but only four directories appear.

## 09-exit-codes — one directory per bit

```
cd scenarios/09-exit-codes
for d in status-*; do (cd "$d" && autocrc >/dev/null 2>&1; echo "$d -> $?"); done
```

`status-1-mismatch` → 1, `status-2-missing` → 2, `status-4-read-error` → 4, and
`status-7-everything` → 7, the three bits together.

## 10-large-files — watching the output arrive

```
cd scenarios/10-large-files && autocrc
```

Three 64 MB files. The `Current directory:` header appears before any hashing
starts and each line lands as its file finishes, rather than everything appearing
at the end. On a directory of 1 GB video files the difference is minutes of
apparent hang.

Compare with `autocrc -q`, which cannot stream: whether a directory is worth
reporting is only known once it has been checked, so a quiet run stays silent and
then prints nothing at all if everything was fine.

## 11-odd-arguments — argument validation

```
cd scenarios/11-odd-arguments
autocrc typo.sfv        # autocrc: typo.sfv: No such file or directory   exit 8
autocrc a-fifo          # autocrc: a-fifo: Not a file or directory       exit 8
autocrc                 # the fifo is skipped, the ordinary file is checked
```

Before 2.0.0 a mistyped path printed `No CRC-sums found` and exited 0, which is
indistinguishable from a clean run. Named explicitly it is now an error; merely
present in a scanned directory, a fifo is still skipped quietly.

## Other things worth trying

```bash
autocrc -q -r .                 # only directories with problems; silent if all is well
autocrc -v scenarios/01-filename-crcs     # mismatches show both sums: ACTUAL != EXPECTED
autocrc --no-crc scenarios/02-sfv-basic   # sfv only, ignore sums in file names
autocrc --no-sfv scenarios/02-sfv-basic   # file names only, ignore the sfv
autocrc -C scenarios/08-recursive alpha   # -C changes directory first, then resolves alpha
autocrc scenarios/01-filename-crcs 02-sfv-basic 08-recursive      # several arguments at once
```

Interrupting a run over `scenarios/10-large-files` with Ctrl-C exits 130.

## Cleaning up

`./build.py --clean` restores the modes on the unreadable directories first. A
plain `rm -rf` will fail on `scenarios/05-permissions/locked-dir` until you run
`chmod -R u+rwX .` yourself.
