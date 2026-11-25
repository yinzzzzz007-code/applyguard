using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

static class Launcher {
    const string PayloadHash = "__PAYLOAD_HASH__";
    static Mutex instanceLock;
    static bool ownsInstance;

    static string Digest(string file) {
        using (var stream = File.OpenRead(file))
        using (var hash = SHA256.Create())
            return BitConverter.ToString(hash.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
    }

    static string CompatibleCache() {
        string system = Path.GetPathRoot(Environment.GetFolderPath(Environment.SpecialFolder.Windows));
        var drives = DriveInfo.GetDrives().Where(d => {
            try { return d.IsReady && d.DriveType == DriveType.Fixed &&
                d.DriveFormat.Equals("NTFS", StringComparison.OrdinalIgnoreCase) && d.AvailableFreeSpace >= 2147483648L; }
            catch { return false; }
        }).OrderBy(d => d.Name.Equals(system, StringComparison.OrdinalIgnoreCase)).ThenByDescending(d => d.AvailableFreeSpace);
        foreach (var drive in drives) {
            try {
                string folder = Path.Combine(drive.Name, "ApplyGuard-cache", "desktop", PayloadHash.Substring(0, 20));
                Directory.CreateDirectory(folder);
                string probe = Path.Combine(folder, ".probe-" + Guid.NewGuid().ToString("N"));
                using (File.Open(probe, FileMode.CreateNew, FileAccess.Write)) {}
                File.Delete(probe);
                return folder;
            } catch (UnauthorizedAccessException) {} catch (IOException) {}
        }
        throw new IOException("未找到至少有 2GB 剩余空间的本机可写 NTFS 缓存目录。资料无需移动。");
    }

    static string Quote(string arg) {
        var result = new StringBuilder("\"");
        int slashes = 0;
        foreach (char ch in arg) {
            if (ch == '\\') { slashes++; continue; }
            if (ch == '"') result.Append('\\', slashes * 2 + 1).Append(ch);
            else result.Append('\\', slashes).Append(ch);
            slashes = 0;
        }
        return result.Append('\\', slashes * 2).Append('"').ToString();
    }

    [STAThread]
    static int Main(string[] args) {
        string home = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        try {
            bool helper = args.Any(arg => arg.StartsWith("--check-", StringComparison.Ordinal) ||
                Path.GetFileName(arg).Equals("agent_mcp.py", StringComparison.OrdinalIgnoreCase) ||
                Path.GetFileName(arg).Equals("connect_harness.py", StringComparison.OrdinalIgnoreCase));
            if (!helper) {
                string identity;
                using (var hash = SHA256.Create())
                    identity = BitConverter.ToString(hash.ComputeHash(Encoding.UTF8.GetBytes(home.ToLowerInvariant()))).Replace("-", "").Substring(0, 24);
                instanceLock = new Mutex(false, "Local\\ApplyGuardWorkspace_" + identity);
                try { ownsInstance = instanceLock.WaitOne(0); } catch (AbandonedMutexException) { ownsInstance = true; }
                if (!ownsInstance) {
                    MessageBox.Show("ApplyGuard 已经打开，请切换到现有窗口继续操作，无需重复启动。", "ApplyGuard", MessageBoxButtons.OK, MessageBoxIcon.Information);
                    return 0;
                }
            }
            string cache = CompatibleCache();
            string core = Path.Combine(cache, "ApplyGuard-core.exe");
            using (var cacheLock = new Mutex(false, "Local\\ApplyGuardPayload_" + PayloadHash.Substring(0, 20))) {
            try { cacheLock.WaitOne(); } catch (AbandonedMutexException) {}
            try {
            if (!File.Exists(core) || Digest(core) != PayloadHash) {
                using (var status = new Form { Text = "ApplyGuard", Width = 460, Height = 145,
                    StartPosition = FormStartPosition.CenterScreen, ControlBox = false }) {
                    status.Controls.Add(new Label { Text = "正在准备本机运行文件，首次启动请稍候…\n您的简历和材料仍保存在原目录。",
                        AutoSize = true, Left = 24, Top = 20 });
                    status.Show(); Application.DoEvents();
                    string temp = Path.Combine(cache, ".payload-" + Guid.NewGuid().ToString("N"));
                    try {
                        using (var input = Assembly.GetExecutingAssembly().GetManifestResourceStream("ApplyGuard.payload"))
                        using (var output = new FileStream(temp, FileMode.CreateNew, FileAccess.Write)) {
                            byte[] buffer = new byte[1048576]; int count;
                            while ((count = input.Read(buffer, 0, buffer.Length)) > 0) {
                                output.Write(buffer, 0, count); Application.DoEvents();
                            }
                        }
                        if (Digest(temp) != PayloadHash) throw new IOException("运行文件校验失败，请重新下载。");
                        if (File.Exists(core)) File.Delete(core);
                        File.Move(temp, core);
                    } finally { if (File.Exists(temp)) File.Delete(temp); }
                    status.Close();
                }
            }
            } finally { cacheLock.ReleaseMutex(); }
            }
            var start = new ProcessStartInfo(core, string.Join(" ", args.Select(Quote).ToArray())) {
                WorkingDirectory = cache, UseShellExecute = false
            };
            start.EnvironmentVariables["APPLYGUARD_DESKTOP_HOME"] = home;
            using (var process = Process.Start(start)) { process.WaitForExit(); return process.ExitCode; }
        } catch (Exception error) {
            string message = "ApplyGuard 启动未完成：" + error.Message;
            try { Directory.CreateDirectory(Path.Combine(home, "ApplyGuard-data"));
                File.AppendAllText(Path.Combine(home, "ApplyGuard-data", "startup.log"), DateTime.Now.ToString("s") + " " + message + "\n"); } catch {}
            MessageBox.Show(message, "ApplyGuard", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        } finally {
            if (ownsInstance) instanceLock.ReleaseMutex();
            if (instanceLock != null) instanceLock.Dispose();
        }
    }
}
