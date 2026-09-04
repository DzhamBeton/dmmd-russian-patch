using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: System.Reflection.AssemblyTitle("DMMD Russian Patch")]
[assembly: System.Reflection.AssemblyProduct("Русификатор DRAMAtical Murder")]
[assembly: System.Reflection.AssemblyVersion("0.1.0.0")]

namespace DmmdRussianPatch
{
    internal sealed class PatchInfo
    {
        public string FileName;
        public string PatchName;
        public PatchInfo(string fileName, string patchName) { FileName = fileName; PatchName = patchName; }
    }

    internal sealed class MainForm : Form
    {
        private readonly TextBox pathBox = new TextBox();
        private readonly Button browseButton = new Button();
        private readonly Button installButton = new Button();
        private readonly Button uninstallButton = new Button();
        private readonly ProgressBar progress = new ProgressBar();
        private readonly TextBox log = new TextBox();
        private readonly PatchInfo[] files = {
            new PatchInfo("script.npk", "script.dmpatch"),
            new PatchInfo("font.npk", "font.dmpatch"),
            new PatchInfo("dx.npk", "dx.dmpatch")
        };

        public MainForm()
        {
            Text = "Русификатор DRAMAtical Murder — v0.1.0";
            ClientSize = new Size(650, 390);
            MinimumSize = new Size(600, 350);
            StartPosition = FormStartPosition.CenterScreen;
            Font = new Font("Segoe UI", 9F);

            Label title = new Label { Text = "Русификатор для GOG Unrated-версии", AutoSize = true, Font = new Font("Segoe UI", 14F, FontStyle.Bold), Location = new Point(18, 16) };
            Label hint = new Label { Text = "Укажите папку, в которой находится DMMd.exe", AutoSize = true, Location = new Point(20, 55) };
            pathBox.Location = new Point(22, 78); pathBox.Width = 520; pathBox.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            browseButton.Text = "Обзор…"; browseButton.Location = new Point(552, 76); browseButton.Width = 78; browseButton.Anchor = AnchorStyles.Top | AnchorStyles.Right;
            installButton.Text = "Установить"; installButton.Location = new Point(22, 116); installButton.Width = 130;
            uninstallButton.Text = "Удалить русификатор"; uninstallButton.Location = new Point(162, 116); uninstallButton.Width = 160;
            progress.Location = new Point(22, 155); progress.Width = 608; progress.Height = 18; progress.Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right;
            log.Location = new Point(22, 187); log.Size = new Size(608, 180); log.Anchor = AnchorStyles.Top | AnchorStyles.Bottom | AnchorStyles.Left | AnchorStyles.Right;
            log.Multiline = true; log.ReadOnly = true; log.ScrollBars = ScrollBars.Vertical; log.BackColor = Color.White;
            Controls.AddRange(new Control[] { title, hint, pathBox, browseButton, installButton, uninstallButton, progress, log });

            browseButton.Click += delegate { Browse(); };
            installButton.Click += delegate { StartWork(true); };
            uninstallButton.Click += delegate { StartWork(false); };
            pathBox.Text = FindGame();
            WriteLog("Патчер не содержит оригинальных файлов игры.");
        }

        private static string FindGame()
        {
            string[] common = {
                @"F:\DRAMAtical Murder",
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles), "GOG Galaxy", "Games", "DRAMAtical Murder"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ProgramFilesX86), "GOG Galaxy", "Games", "DRAMAtical Murder"),
                @"C:\GOG Games\DRAMAtical Murder"
            };
            foreach (string path in common) if (File.Exists(Path.Combine(path, "DMMd.exe"))) return path;
            return "";
        }

        private void Browse()
        {
            using (FolderBrowserDialog dialog = new FolderBrowserDialog())
            {
                dialog.Description = "Выберите папку DRAMAtical Murder";
                dialog.SelectedPath = pathBox.Text;
                if (dialog.ShowDialog(this) == DialogResult.OK) pathBox.Text = dialog.SelectedPath;
            }
        }

        private void StartWork(bool install)
        {
            string gamePath = pathBox.Text.Trim().Trim('"');
            if (!File.Exists(Path.Combine(gamePath, "DMMd.exe")))
            {
                MessageBox.Show(this, "В выбранной папке не найден DMMd.exe.", "Неверная папка", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            SetBusy(true);
            Thread thread = new Thread(delegate()
            {
                try
                {
                    if (Process.GetProcessesByName("DMMd").Length != 0) throw new InvalidOperationException("Сначала закройте игру.");
                    if (install) Install(gamePath); else Uninstall(gamePath);
                    Invoke((MethodInvoker)delegate { MessageBox.Show(this, install ? "Русификатор успешно установлен." : "Оригинальные файлы восстановлены.", "Готово", MessageBoxButtons.OK, MessageBoxIcon.Information); });
                }
                catch (Exception ex)
                {
                    WriteLog("ОШИБКА: " + ex.Message);
                    Invoke((MethodInvoker)delegate { MessageBox.Show(this, ex.Message, "Ошибка", MessageBoxButtons.OK, MessageBoxIcon.Error); });
                }
                finally { SetBusy(false); }
            });
            thread.IsBackground = true;
            thread.Start();
        }

        private void Install(string gamePath)
        {
            string payload = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "payload");
            foreach (PatchInfo item in files)
            {
                string target = Path.Combine(gamePath, item.FileName);
                string backup = target + ".dmmd-rus-backup";
                ValidateCompatibility(target, Path.Combine(payload, item.PatchName), backup);
            }
            for (int i = 0; i < files.Length; i++)
            {
                PatchInfo item = files[i];
                string target = Path.Combine(gamePath, item.FileName);
                string patch = Path.Combine(payload, item.PatchName);
                string backup = target + ".dmmd-rus-backup";
                SetProgress(i * 100 / files.Length);
                WriteLog("Проверка " + item.FileName + "…");
                if (!File.Exists(patch)) throw new FileNotFoundException("Не найден файл патча: " + item.PatchName);
                ApplyPatch(target, patch, backup);
                WriteLog(item.FileName + " — готово.");
            }
            SetProgress(100);
        }

        private void Uninstall(string gamePath)
        {
            foreach (PatchInfo item in files)
            {
                string backup = Path.Combine(gamePath, item.FileName) + ".dmmd-rus-backup";
                if (!File.Exists(backup)) throw new FileNotFoundException("Не найдена резервная копия " + Path.GetFileName(backup));
            }
            for (int i = 0; i < files.Length; i++)
            {
                string target = Path.Combine(gamePath, files[i].FileName);
                string backup = target + ".dmmd-rus-backup";
                SetProgress(i * 100 / files.Length);
                if (!File.Exists(backup)) throw new FileNotFoundException("Не найдена резервная копия " + Path.GetFileName(backup));
                string temp = target + ".dmmd-rus-restore";
                File.Copy(backup, temp, true);
                File.Delete(target);
                File.Move(temp, target);
                File.Delete(backup);
                WriteLog(files[i].FileName + " — восстановлен.");
            }
            SetProgress(100);
        }

        internal static void ApplyPatch(string target, string patchPath, string backup)
        {
            if (!File.Exists(target)) throw new FileNotFoundException("Не найден " + Path.GetFileName(target));
            string temp = target + ".dmmd-rus-tmp";
            if (File.Exists(temp)) File.Delete(temp);
            try
            {
                using (BinaryReader patch = new BinaryReader(File.OpenRead(patchPath)))
                {
                    if (Encoding.ASCII.GetString(patch.ReadBytes(4)) != "DMP1") throw new InvalidDataException("Повреждён файл патча.");
                    long sourceSize = patch.ReadInt64();
                    long targetSize = patch.ReadInt64();
                    byte[] sourceHash = patch.ReadBytes(32);
                    byte[] targetHash = patch.ReadBytes(32);
                    int count = patch.ReadInt32();
                    FileInfo info = new FileInfo(target);
                    byte[] currentHash = HashFile(target);
                    if (BytesEqual(currentHash, targetHash)) return;
                    if (info.Length != sourceSize || !BytesEqual(currentHash, sourceHash))
                        throw new InvalidDataException(Path.GetFileName(target) + " не соответствует поддерживаемой GOG Unrated-версии или уже изменён другим модом.");
                    if (!File.Exists(backup)) File.Copy(target, backup);
                    File.Copy(target, temp, true);
                    using (FileStream output = new FileStream(temp, FileMode.Open, FileAccess.Write, FileShare.None))
                    {
                        output.SetLength(targetSize);
                        for (int i = 0; i < count; i++)
                        {
                            long offset = patch.ReadInt64();
                            int length = patch.ReadInt32();
                            output.Position = offset;
                            CopyExactly(patch.BaseStream, output, length);
                        }
                    }
                    if (!BytesEqual(HashFile(temp), targetHash)) throw new InvalidDataException("Контрольная сумма результата не совпала.");
                }
                File.Delete(target);
                File.Move(temp, target);
            }
            finally { if (File.Exists(temp)) File.Delete(temp); }
        }

        private static void ValidateCompatibility(string target, string patchPath, string backup)
        {
            if (!File.Exists(target)) throw new FileNotFoundException("Не найден " + Path.GetFileName(target));
            if (!File.Exists(patchPath)) throw new FileNotFoundException("Не найден файл патча: " + Path.GetFileName(patchPath));
            using (BinaryReader patch = new BinaryReader(File.OpenRead(patchPath)))
            {
                if (Encoding.ASCII.GetString(patch.ReadBytes(4)) != "DMP1") throw new InvalidDataException("Повреждён файл патча.");
                long sourceSize = patch.ReadInt64();
                patch.ReadInt64();
                byte[] sourceHash = patch.ReadBytes(32);
                byte[] targetHash = patch.ReadBytes(32);
                FileInfo info = new FileInfo(target);
                byte[] currentHash = HashFile(target);
                if (BytesEqual(currentHash, targetHash))
                {
                    if (!File.Exists(backup)) throw new InvalidDataException(Path.GetFileName(target) + " уже изменён, но резервная копия отсутствует.");
                    return;
                }
                if (info.Length != sourceSize || !BytesEqual(currentHash, sourceHash))
                    throw new InvalidDataException(Path.GetFileName(target) + " не соответствует поддерживаемой GOG Unrated-версии или уже изменён другим модом.");
            }
        }

        private static void CopyExactly(Stream input, Stream output, int bytes)
        {
            byte[] buffer = new byte[1024 * 1024];
            while (bytes > 0)
            {
                int read = input.Read(buffer, 0, Math.Min(buffer.Length, bytes));
                if (read == 0) throw new EndOfStreamException();
                output.Write(buffer, 0, read);
                bytes -= read;
            }
        }

        private static byte[] HashFile(string path)
        {
            using (SHA256 sha = SHA256.Create())
            using (FileStream input = File.OpenRead(path)) return sha.ComputeHash(input);
        }

        private static bool BytesEqual(byte[] a, byte[] b)
        {
            if (a.Length != b.Length) return false;
            int diff = 0; for (int i = 0; i < a.Length; i++) diff |= a[i] ^ b[i];
            return diff == 0;
        }

        private void WriteLog(string text)
        {
            if (InvokeRequired) { Invoke((MethodInvoker)delegate { WriteLog(text); }); return; }
            log.AppendText(text + Environment.NewLine);
        }

        private void SetProgress(int value)
        {
            if (InvokeRequired) { Invoke((MethodInvoker)delegate { SetProgress(value); }); return; }
            progress.Value = Math.Max(0, Math.Min(100, value));
        }

        private void SetBusy(bool busy)
        {
            if (InvokeRequired) { Invoke((MethodInvoker)delegate { SetBusy(busy); }); return; }
            installButton.Enabled = uninstallButton.Enabled = browseButton.Enabled = pathBox.Enabled = !busy;
        }
    }

    internal static class Program
    {
        [STAThread]
        private static void Main(string[] args)
        {
            if (args.Length == 4 && args[0] == "--apply")
            {
                try { MainForm.ApplyPatch(args[1], args[2], args[3]); }
                catch { Environment.ExitCode = 1; }
                return;
            }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm());
        }
    }
}
