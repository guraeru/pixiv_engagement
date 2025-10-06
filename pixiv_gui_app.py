# pixiv_gui_app.py

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
import sys

# ロジックモジュールをインポート
# 同じディレクトリに pixiv_analyzer_core.py が必要
try:
    from pixivpy3.PixivRankAnalyzer import (
        PixivRankAnalyzer, 
        RankingMode, 
        ContentType, 
        RankPresetManager,
        setup_logging
    )
except ImportError as e:
    # 依存関係エラー
    print("エラー: pixiv_analyzer_core.py が見つからないか、内部でエラーが発生しました。")
    print(f"詳細: {e}")
    sys.exit(1)


# --- ロギングと標準出力リダイレクト設定 ---

# 標準出力をロガーにリダイレクトするためのヘルパークラス
class StreamRedirector:
    """print()などの標準出力をロガーにリダイレクトする"""
    def __init__(self, logger):
        self.logger = logger

    def write(self, buf):
        # bufが空でない、かつ改行文字だけでない場合にログに出力
        if buf.strip():
            # print()はINFOレベルでログに流す
            self.logger.info(buf.rstrip())

    def flush(self):
        pass

# --- GUIクラスの定義 ---

class PixivApp(tk.Tk):
    """Tkinterを使用したPixivランキング分析GUIアプリケーション"""

    def __init__(self):
        super().__init__()
        self.title("Pixiv エンゲージメント分析ツール (Tkinter)")
        self.geometry("800x500")
        
        self.analyzer = None  # PixivRankAnalyzerのインスタンスを保持
        self.current_results = [] # 取得したランキング結果を保持
        
        # 変数の初期化
        self.mode_var = tk.StringVar(value=RankingMode.DAILY.name)
        self.content_var = tk.StringVar(value=ContentType.ILLUST.name)
        
        # プリセット値を初期値として設定
        initial_views, initial_bookmarks = RankPresetManager.get_preset(RankingMode.DAILY.name)
        self.views_var = tk.StringVar(value=initial_views)
        self.bookmarks_var = tk.StringVar(value=initial_bookmarks)
        self.dl_count_var = tk.StringVar(value="10")
        
        self._setup_ui()

    def _setup_ui(self):
        # ... (中略: UIの配置ロジックは変更なし) ...
        
        # 1. 設定フレーム
        settings_frame = ttk.LabelFrame(self, text="設定", padding="10")
        settings_frame.pack(padx=10, pady=5, fill="x")
        
        self._create_setting_widgets(settings_frame)
        
        # 2. ランキング表示フレーム (Treeviewを使用)
        results_frame = ttk.Frame(self, padding="10")
        results_frame.pack(padx=10, pady=5, fill="both", expand=True)

        self.result_tree = self._create_result_treeview(results_frame)
        self.result_tree.pack(fill="both", expand=True)
        
        # 3. 実行ボタン
        self.run_button = ttk.Button(self, text="🚀 ランキング取得", command=self._start_ranking_fetch_thread)
        self.run_button.pack(padx=10, pady=5, fill="x")
        
        # 4. ダウンロードボタン
        self.download_button = ttk.Button(self, text="✅ トップ作品をダウンロード", command=self._start_download_thread, state=tk.DISABLED)
        self.download_button.pack(padx=10, pady=5, fill="x")
        
        # モード変更時のイベントバインド
        self.mode_var.trace_add("write", self._update_presets_from_trace)


    def _update_presets_from_trace(self, *args):
        self.update_presets()
        
    def update_presets(self):
        """ランキングモードの選択に応じて、最小閲覧数と最小ブックマーク数のプリセットを更新する"""
        mode_name = self.mode_var.get()
        views, bookmarks = RankPresetManager.get_preset(mode_name)
        
        self.views_var.set(views)
        self.bookmarks_var.set(bookmarks)


    def _create_setting_widgets(self, parent_frame):
        """設定項目のGUIウィジェットを作成"""
        
        labels = ["モード:", "コンテンツ:", "最小閲覧数:", "最小B!数:", "DL数:"]
        vars = [self.mode_var, self.content_var, self.views_var, self.bookmarks_var, self.dl_count_var]
        
        row = ttk.Frame(parent_frame)
        row.pack(fill="x", pady=2)

        # モード (Combobox)
        ttk.Label(row, text=labels[0]).pack(side="left", padx=5)
        mode_combo = ttk.Combobox(row, textvariable=vars[0], values=[e.name for e in RankingMode], state="readonly", width=12)
        mode_combo.pack(side="left", padx=5)
        
        # コンテンツ (Combobox)
        ttk.Label(row, text=labels[1]).pack(side="left", padx=5)
        content_combo = ttk.Combobox(row, textvariable=vars[1], values=[e.name for e in ContentType], state="readonly", width=8)
        content_combo.pack(side="left", padx=5)

        # 閲覧数 (Entry)
        ttk.Label(row, text=labels[2]).pack(side="left", padx=5)
        ttk.Entry(row, textvariable=vars[2], width=8).pack(side="left", padx=5)
        
        # ブックマーク数 (Entry)
        ttk.Label(row, text=labels[3]).pack(side="left", padx=5)
        ttk.Entry(row, textvariable=vars[3], width=8).pack(side="left", padx=5)
        
        # ダウンロード数 (Entry)
        ttk.Label(row, text=labels[4]).pack(side="left", padx=5)
        ttk.Entry(row, textvariable=vars[4], width=5).pack(side="left", padx=5)


    def _create_result_treeview(self, parent_frame):
        """ランキング表示用のTreeviewウィジェットを作成"""
        columns = ("#", "率(%)", "B!数", "閲覧数", "作者名", "タイトル")
        tree = ttk.Treeview(parent_frame, columns=columns, show="headings")
        
        vsb = ttk.Scrollbar(parent_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        widths = [30, 60, 80, 80, 120, 400]
        for col, width in zip(columns, widths):
            tree.heading(col, text=col, anchor="center")
            tree.column(col, anchor="center", width=width)
        
        tree.column("タイトル", anchor="w")
        return tree

    def _set_buttons_enabled(self, run_enabled: bool, dl_enabled: bool):
        """ボタンの有効/無効状態を一括で設定"""
        self.run_button.config(state=tk.NORMAL if run_enabled else tk.DISABLED)
        self.download_button.config(state=tk.NORMAL if dl_enabled else tk.DISABLED)
        
    # --- ランキング取得処理 (スレッド化) ---

    def _start_ranking_fetch_thread(self):
        """ランキング取得処理を別スレッドで開始"""
        
        try:
            mode = RankingMode[self.mode_var.get()]
            content = ContentType[self.content_var.get()]
            min_views = int(self.views_var.get())
            min_bookmarks = int(self.bookmarks_var.get())
            dl_count = int(self.dl_count_var.get())
            
        except (ValueError, KeyError):
            messagebox.showerror("入力エラー", "設定値を確認してください。閲覧数、B!数、DL数は有効な整数が必要です。")
            return

        self._set_buttons_enabled(False, False)
        self.run_button.config(text="データ取得中...")
        self.result_tree.delete(*self.result_tree.get_children())
        
        self.analyzer = PixivRankAnalyzer(
            ranking_mode=mode,
            content_type=content,
            min_views=min_views,
            min_bookmarks=min_bookmarks,
            download_count=dl_count,
            enable_download=True 
        )

        thread = threading.Thread(target=self._ranking_fetch_worker, daemon=True)
        thread.start()

    def _ranking_fetch_worker(self):
        """別スレッドで実行されるAPI処理"""
        try:
            self.analyzer.authenticate()
            results = self.analyzer.calculate_engagement()
            
            self.after(0, lambda: self._on_fetch_finished(results))

        except Exception as e:
            logging.error(f"APIエラー: {e}")
            self.after(0, lambda: self._on_fetch_error(str(e)))
            
    def _on_fetch_finished(self, results: list):
        """データ取得完了後の処理 (メインスレッドで実行)"""
        self.run_button.config(text="🚀 ランキング取得")
        self.current_results = results
        self._display_results_in_treeview(results)
        
        if not results:
            messagebox.showinfo("結果", "指定された条件に一致する作品は見つかりませんでした。")
            self._set_buttons_enabled(True, False)
        else:
            self._set_buttons_enabled(True, True)

    def _on_fetch_error(self, message: str):
        """エラー発生時の処理 (メインスレッドで実行)"""
        self.run_button.config(text="🚀 ランキング取得")
        self._set_buttons_enabled(True, False)
        messagebox.showerror("APIエラー", f"ランキング取得中にエラーが発生しました。\n詳細: {message}")

    def _display_results_in_treeview(self, results: list):
        """取得した結果をTreeviewに表示"""
        for i, item in enumerate(results[:50]):
            data = (
                f"#{i+1:02d}",
                f"{item['rate']:.2f}%",
                f"{item['bookmark']:,}",
                f"{item['view']:,}",
                item['user_name'],
                item['title']
            )
            self.result_tree.insert("", "end", values=data)
    
    # --- ダウンロード処理 (スレッド化) ---
    
    def _start_download_thread(self):
        """ダウンロード処理を別スレッドで開始"""
        if not self.current_results:
            messagebox.showwarning("警告", "先にランキングデータを取得してください。")
            return
            
        self._set_buttons_enabled(False, False)
        self.download_button.config(text="ダウンロード中...")

        thread = threading.Thread(target=self._download_worker, daemon=True)
        thread.start()
        
    def _download_worker(self):
        """別スレッドで実行されるダウンロード処理"""
        try:
            self.analyzer.download_images(self.current_results)
            self.after(0, self._on_download_finished)

        except Exception as e:
            logging.error(f"ダウンロード中に予期せぬエラーが発生しました: {e}")
            self.after(0, lambda: self._on_download_error(str(e)))
            
    def _on_download_finished(self):
        """ダウンロード完了後の処理 (メインスレッドで実行)"""
        self.download_button.config(text="✅ トップ作品をダウンロード")
        self._set_buttons_enabled(True, True)
        
        messagebox.showinfo("ダウンロード完了", 
                            f"トップ {self.analyzer.download_count} 件の作品のダウンロードが完了しました。\n"
                            f"保存先: {self.analyzer.download_dir}\n"
                            "詳細はログファイル (pixiv_analysis.log) を確認してください。")

    def _on_download_error(self, message: str):
        """ダウンロードエラー発生時の処理 (メインスレッドで実行)"""
        self.download_button.config(text="✅ トップ作品をダウンロード")
        self._set_buttons_enabled(True, True)
        messagebox.showerror("ダウンロードエラー", f"ダウンロード中にエラーが発生しました。\n詳細: {message}")


# ====================================================================
# アプリケーションのエントリポイント
# ====================================================================
if __name__ == "__main__":
    # ロギング設定の初期化
    setup_logging() 
    
    # Analyzerクラスのprint()出力をログファイルにリダイレクト
    # 'stdout_redirect' ロガーは、setup_loggingで定義したハンドラを使用
    sys.stdout = StreamRedirector(logging.getLogger('stdout_redirect'))
    
    app = PixivApp()
    app.mainloop()