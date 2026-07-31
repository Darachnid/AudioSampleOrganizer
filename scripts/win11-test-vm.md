# Win11 VM testing for ClipMark

Use this to verify `setup.bat` and `run.bat` on a real Windows cmd environment.

## What you already have

- Win11 disk: `/var/lib/libvirt/images/win11.qcow2`
- Win11 ISO (if you need a fresh install): `~/Downloads/Win11_25H2_English_x64_v2.iso`
- `qemu-system-x86_64`, `virt-manager`, `virsh`

## Option A: Existing Win11 disk (fastest)

You already have a libvirt domain named **`win11`** and disk at
`/var/lib/libvirt/images/win11.qcow2`.

From the project root:

```bash
chmod +x scripts/start-win11-test-vm.sh
./scripts/start-win11-test-vm.sh
virt-viewer win11
```

Or open **virt-manager** and start **win11** from there.

Inside Windows:

1. Open **Command Prompt** or **Windows Terminal**
2. Get the ClipMark folder onto the VM:
   - virtiofs share `\\ClipMark` (after guest tools), or
   - `git clone <repo-url>`, or
   - copy the folder via USB/shared folder
3. Run:

```bat
cd C:\path\to\ClipMark
setup.bat
run.bat
```

4. Paste a WAV path when prompted, for example:

```bat
C:\Users\Public\test.wav
```

## Option B: Create VM in virt-manager (manual, most reliable)

1. Open **virt-manager** → **New Virtual Machine**
2. Choose **Import existing disk image**
3. Select `/var/lib/libvirt/images/win11.qcow2`
4. OS: **Microsoft Windows 11**
5. UEFI + TPM enabled (required for Win11)
6. Add a **Filesystem** device pointing at this ClipMark folder (virtiofs)
7. Finish and boot

## What to verify

- [ ] `setup.bat` completes without errors
- [ ] `run.bat` opens the ClipMark UI
- [ ] WAV path with backslashes works
- [ ] Arrow keys, Space, A/D, Enter, Q work in cmd/Windows Terminal
- [ ] Export writes to `ExportedSamples\`

## Common Windows failures

| Symptom | Fix |
|---------|-----|
| `python is not recognized` | Reinstall Python with **Add to PATH** checked |
| `No module named 'curses'` | Re-run `setup.bat` (installs `windows-curses`) |
| Blank or broken UI | Use Windows Terminal, not an IDE run panel |
| No audio | Check default playback device in Windows sound settings |

## Send this to Cat

After you confirm in the VM, she only needs:

1. Python installed (PATH checked)
2. The ClipMark folder
3. `setup.bat` once
4. `run.bat` every time
