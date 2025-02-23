import os
import requests
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from m3u8 import M3U8
from Crypto.Cipher import AES
from tkinter import Tk, Label, Entry, Button, filedialog, messagebox
from tkinter.ttk import Progressbar
import threading

class M3U8Downloader:
    def __init__(self, m3u8_url="", output_file="output.mp4", max_workers=10):
        self.m3u8_url = m3u8_url
        self.output_file = output_file
        self.max_workers = max_workers
        self.temp_dir = "temp_ts"
        self.key = None
        self.iv = None
        self.total_segments = 0
        self.progress = 0
        self.cancel_flag = False

    def _download(self, url, filename, retry=3):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
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

    def _get_full_url(self, uri):
        return urljoin(self.m3u8_url, uri)

    def _download_key(self, key_uri):
        key_url = self._get_full_url(key_uri)
        self.key = requests.get(key_url).content

    def _decrypt_ts(self, data):
        if self.key and self.iv:
            cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
            return cipher.decrypt(data)
        return data

    def _download_segment(self, segment, index):
        try:
            ts_url = self._get_full_url(segment.uri)
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
        content = requests.get(self.m3u8_url).text
        m3u8_obj = M3U8(content, base_uri=self.m3u8_url)
        if m3u8_obj.keys and m3u8_obj.keys[0]:
            key_info = m3u8_obj.keys[0]
            self._download_key(key_info.uri)
            self.iv = key_info.iv or self.key[:16]
        self.total_segments = len(m3u8_obj.segments)
        return m3u8_obj.segments

    def _merge_files(self, file_list):
        try:
            with open(self.output_file, "wb") as output:
                for file in file_list:
                    with open(file, "rb") as f:
                        output.write(f.read())
            messagebox.showinfo("下载完成", f"文件已保存到 {self.output_file}")
        except Exception as e:
            messagebox.showerror("合并失败", f"合并文件时出错: {str(e)}")

    def _cleanup(self):
        if os.path.exists(self.temp_dir):
            for file in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, file))
            os.rmdir(self.temp_dir)

    def start_download(self):
        self.progress = 0
        self._prepare()
        segments = self._parse_m3u8()
        if not segments:
            print("没有找到TS片段")
            return

        file_list = [None] * len(segments)  # 预分配列表
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self._download_segment, seg, i): i for i, seg in enumerate(segments)}
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
            messagebox.showinfo("下载取消", "下载已被取消。")

    def update_progress_bar(self):
        self.progress_bar['value'] = (self.progress / self.total_segments) * 100
        self.progress_label.config(text=f"下载进度: {self.progress_bar['value']}%")
        self.window.update_idletasks()

    def open_file_dialog(self):
        self.output_file = filedialog.asksaveasfilename(defaultextension=".mp4",
                                                       filetypes=[("MP4 files", "*.mp4")])
        self.output_path_entry.delete(0, 'end')
        self.output_path_entry.insert(0, self.output_file)

    def create_gui(self):
        self.window = Tk()
        self.window.title("M3U8 Downloader")

        Label(self.window, text="M3U8 URL:").grid(row=0, column=0, padx=10, pady=5)
        self.m3u8_url_entry = Entry(self.window, width=50)
        self.m3u8_url_entry.grid(row=0, column=1, padx=10, pady=5)

        Label(self.window, text="保存路径:").grid(row=1, column=0, padx=10, pady=5)
        self.output_path_entry = Entry(self.window, width=50)
        self.output_path_entry.grid(row=1, column=1, padx=10, pady=5)
        Button(self.window, text="选择路径", command=self.open_file_dialog).grid(row=1, column=2, padx=10, pady=5)

        self.progress_bar = Progressbar(self.window, orient="horizontal", length=300, mode="determinate")
        self.progress_bar.grid(row=2, column=0, columnspan=3, padx=10, pady=20)

        self.progress_label = Label(self.window, text="下载进度: 0%")
        self.progress_label.grid(row=3, column=0, columnspan=3, padx=10, pady=5)

        self.download_button = Button(self.window, text="开始下载", command=self.start_download_thread)
        self.download_button.grid(row=4, column=0, columnspan=2, padx=10, pady=10)

        self.cancel_button = Button(self.window, text="取消下载", command=self.cancel_download)
        self.cancel_button.grid(row=4, column=2, padx=10, pady=10)

        self.window.mainloop()

    def start_download_thread(self):
        self.m3u8_url = self.m3u8_url_entry.get()
        self.output_file = self.output_path_entry.get()
        if not self.m3u8_url or not self.output_file:
            messagebox.showwarning("输入错误", "请确保M3U8 URL和保存路径都已填写。")
            return
        threading.Thread(target=self.start_download).start()

    def cancel_download(self):
        self.cancel_flag = True

if __name__ == "__main__":
    downloader = M3U8Downloader(max_workers=20)
    downloader.create_gui()
