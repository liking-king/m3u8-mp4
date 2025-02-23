import os
import requests
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from m3u8 import M3U8
from Crypto.Cipher import AES
from tkinter import Tk, Label, Entry, Button, filedialog, messagebox, Text, Spinbox
from tkinter.ttk import Progressbar
import threading

class M3U8Downloader:
    def __init__(self):
        self.m3u8_urls = []
        self.output_file = "output.mp4"
        self.max_workers = 20
        self.temp_dir = "temp_ts"
        self.key = None
        self.iv = None
        self.total_segments = 0
        self.progress = 0
        self.cancel_flag = False
        self.window = None

    def _download(self, url, filename, retry=3):
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            with open(filename, "wb") as f:
                f.write(response.content)
            return True
        except Exception as e:
            if retry > 0:
                return self._download(url, filename, retry - 1)
            print(f"下载失败: {url}")
            return False

    def _get_full_url(self, base_url, uri):
        return urljoin(base_url, uri)

    def _download_key(self, key_uri, base_url):
        key_url = self._get_full_url(base_url, key_uri)
        self.key = requests.get(key_url).content

    def _decrypt_ts(self, data):
        if self.key and self.iv:
            cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
            return cipher.decrypt(data)
        return data

    def _download_segment(self, segment, index, base_url):
        try:
            ts_url = self._get_full_url(base_url, segment.uri)
            filename = os.path.join(self.temp_dir, f"segment_{index}.ts")
            if not self._download(ts_url, filename):
                return None
            with open(filename, "rb") as f:
                data = f.read()
            decrypted_data = self._decrypt_ts(data)
            with open(filename, "wb") as f:
                f.write(decrypted_data)
            self.progress += 1
            self.update_progress_bar()
            return filename
        except Exception as e:
            print(f"下载片段失败: {str(e)}")
            return None

    def _prepare(self):
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

    def _parse_m3u8(self):
        all_segments = []
        for url in self.m3u8_urls:
            content = requests.get(url).text
            m3u8_obj = M3U8(content, base_uri=url)
            if m3u8_obj.keys and m3u8_obj.keys[0] and not self.key:
                key_info = m3u8_obj.keys[0]
                self._download_key(key_info.uri, url)
                self.iv = key_info.iv or self.key[:16]
            all_segments.extend([(seg, url) for seg in m3u8_obj.segments])
        self.total_segments = len(all_segments)
        return all_segments

    def _merge_files(self, file_list):
        try:
            with open(self.output_file, "wb") as output:
                for file in file_list:
                    with open(file, "rb") as f:
                        output.write(f.read())
            messagebox.showinfo("完成", f"文件已保存到 {self.output_file}")
        except Exception as e:
            messagebox.showerror("错误", f"合并失败: {str(e)}")

    def _cleanup(self):
        if os.path.exists(self.temp_dir):
            for file in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, file))
            os.rmdir(self.temp_dir)

    def start_download(self):
        self.progress = 0
        self._prepare()
        segments_with_url = self._parse_m3u8()
        if not segments_with_url:
            messagebox.showwarning("错误", "未找到TS片段")
            return

        file_list = [None] * len(segments_with_url)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._download_segment, seg, i, base_url): i
                for i, (seg, base_url) in enumerate(segments_with_url)
            }
            for future in as_completed(futures):
                if self.cancel_flag:
                    break
                result = future.result()
                index = futures[future]
                if result:
                    file_list[index] = result

        if not self.cancel_flag:
            self._merge_files([f for f in file_list if f])
            self._cleanup()
        else:
            messagebox.showinfo("取消", "下载已取消")
        self.cancel_flag = False

    def update_progress_bar(self):
        progress_percent = (self.progress / self.total_segments) * 100
        self.progress_bar['value'] = progress_percent
        self.progress_label.config(text=f"进度: {progress_percent:.1f}%")
        self.window.update_idletasks()

    def open_file_dialog(self):
        self.output_file = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[("MP4文件", "*.mp4")]
        )
        self.output_path_entry.delete(0, 'end')
        self.output_path_entry.insert(0, self.output_file)

    def create_gui(self):
        self.window = Tk()
        self.window.title("M3U8下载器")

        # URL输入区
        Label(self.window, text="M3U8链接（每行一个）:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.m3u8_urls_text = Text(self.window, height=8, width=60)
        self.m3u8_urls_text.grid(row=0, column=1, padx=10, pady=5, columnspan=2)

        # 保存路径
        Label(self.window, text="保存路径:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.output_path_entry = Entry(self.window, width=50)
        self.output_path_entry.grid(row=1, column=1, padx=10, pady=5)
        Button(self.window, text="浏览", command=self.open_file_dialog).grid(row=1, column=2, padx=10, pady=5)

        # 线程设置
        Label(self.window, text="下载线程数:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.thread_spinbox = Spinbox(self.window, from_=1, to=50, width=5)
        self.thread_spinbox.delete(0, "end")
        self.thread_spinbox.insert(0, "20")
        self.thread_spinbox.grid(row=2, column=1, padx=10, pady=5, sticky="w")

        # 进度条
        self.progress_bar = Progressbar(self.window, orient="horizontal", length=400, mode="determinate")
        self.progress_bar.grid(row=3, column=0, columnspan=3, padx=10, pady=15)

        # 进度标签
        self.progress_label = Label(self.window, text="进度: 0.0%")
        self.progress_label.grid(row=4, column=0, columnspan=3, padx=10, pady=5)

        # 控制按钮
        Button(self.window, text="开始下载", command=self.start_download_thread, width=15).grid(row=5, column=1, pady=10)
        Button(self.window, text="取消下载", command=self.cancel_download, width=15).grid(row=5, column=2, pady=10)

        self.window.mainloop()

    def start_download_thread(self):
        # 验证线程数
        try:
            self.max_workers = int(self.thread_spinbox.get())
            if not 1 <= self.max_workers <= 50:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "线程数必须为1-50的整数")
            return

        # 获取输入参数
        urls = self.m3u8_urls_text.get("1.0", "end-1c").strip().splitlines()
        self.m3u8_urls = [url.strip() for url in urls if url.strip()]
        self.output_file = self.output_path_entry.get()

        # 输入校验
        if not self.m3u8_urls:
            messagebox.showwarning("错误", "至少需要输入一个M3U8链接")
            return
        if not self.output_file:
            messagebox.showwarning("错误", "请选择保存路径")
            return

        threading.Thread(target=self.start_download).start()

    def cancel_download(self):
        self.cancel_flag = True

if __name__ == "__main__":
    downloader = M3U8Downloader()
    downloader.create_gui()