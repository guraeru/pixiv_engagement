# pixiv_analyzer_core.py

import logging
import os
import sys
import random 
import time
import re
from unicodedata import normalize
from typing import Tuple 
from enum import Enum

# pixivpy3は外部ライブラリなので、別途インストールが必要です
try:
    from pixivpy3 import AppPixivAPI
except ImportError:
    # GUI側でエラーメッセージを出すため、ここではloggingのみ
    logging.critical("エラー: pixivpy3 ライブラリが見つかりません。")
    sys.exit(1)


# --- 1. 列挙型 (Enum) の定義 ---

class RankingMode(Enum):
    # APIモード文字列のみを値として保持
    DAILY = 'day'
    WEEKLY = 'week'
    MONTHLY = 'month'
    DAILY_AI = 'day_ai'
    DAILY_MALE = 'day_male'
    DAILY_FEMALE = 'day_female'
    WEEKLY_ORIGINAL = 'week_original'

class ContentType(Enum):
    ALL = 'all'
    ILLUST = 'illust'
    MANGA = 'manga'

# --- 1.5. ランキングモードごとの推奨値 (プリセット) 定義 ---

class RankPresetManager:
    """ RankingModeに基づいて、推奨される最小閲覧数と最小ブックマーク数を管理するクラス。 """
    PRESETS = {
        RankingMode.DAILY.name:        ("1000", "1000"),
        RankingMode.DAILY_MALE.name:   ("1000", "1000"),
        RankingMode.DAILY_FEMALE.name: ("1000", "1000"),
        RankingMode.DAILY_AI.name:     ("1000", "1000"),
        RankingMode.WEEKLY.name:       ("5000", "2000"),
        RankingMode.WEEKLY_ORIGINAL.name: ("1000", "1000"),
        RankingMode.MONTHLY.name:      ("10000", "5000"), 
    }
    
    @staticmethod
    def get_preset(mode_name: str) -> Tuple[str, str]:
        """ RankingModeの.name (文字列) を受け取り、対応するプリセット値 (最小閲覧数、最小B!数) を返す。 """
        return RankPresetManager.PRESETS.get(mode_name, ("1000", "100"))

# --- 2. Pixiv解析機能のクラス化 ---

class PixivRankAnalyzer:
    
    def __init__(self, 
                 ranking_mode: RankingMode, 
                 content_type: ContentType, 
                 min_views: int, 
                 min_bookmarks: int, 
                 download_count: int, 
                 enable_download: bool = True):
        
        self.ranking_mode = ranking_mode
        self.content_type = content_type
        self.min_views_threshold = min_views
        self.min_bookmarks_threshold = min_bookmarks
        self.download_count = download_count
        self.enable_download = enable_download
        self.api = None
        
        self.download_dir = self._generate_download_dir_name()
        
    # --- ユーティリティメソッド ---
    @staticmethod
    def _sanitize_filename(text, max_length=30):
        s = text.replace('\n', ' ')
        s = re.sub(r'[\\/:*?"<>|]', 'ー', s)
        s = re.sub(r'[\u0000-\u001f]', '', s)
        s = s.strip()
        s = normalize('NFKC', s)
        return s[:max_length]

    @staticmethod
    def _get_mode_name_japanese(mode):
        return {
             RankingMode.DAILY: '日間', RankingMode.WEEKLY: '週間', 
             RankingMode.MONTHLY: '月間', 
             RankingMode.DAILY_MALE: '男性人気', RankingMode.DAILY_FEMALE: '女性人気',
             RankingMode.DAILY_AI: '日間AI',
             RankingMode.WEEKLY_ORIGINAL: '週間オリジナル'
        }.get(mode, mode.name)

    @staticmethod
    def _get_content_name_japanese(content):
        return {
             ContentType.ILLUST: 'イラスト', ContentType.MANGA: 'マンガ', 
             ContentType.ALL: 'すべて'
        }.get(content, content.name)

    @staticmethod
    def _to_k_unit(value):
        if value < 1000:
            return f"{value}"
        return f"{int(value / 1000)}K"

    def _generate_download_dir_name(self):
        mode_jp = self._get_mode_name_japanese(self.ranking_mode)
        content_jp = self._get_content_name_japanese(self.content_type)
        
        view_str = f"閲覧{self._to_k_unit(self.min_views_threshold)}" if self.min_views_threshold > 0 else ""
        bmark_str = f"ブクマ{self._to_k_unit(self.min_bookmarks_threshold)}" if self.min_bookmarks_threshold > 0 else ""
        
        filter_parts = [p for p in [mode_jp, content_jp, view_str, bmark_str] if p]
        dir_name = "_".join(filter_parts)
        
        return os.path.join("ダウンロード_作品分析", dir_name)
    
    @staticmethod
    def _rand_sleep():
        delay = random.uniform(1, 3)
        time.sleep(delay)
        logging.debug(f"Sleep for {delay:.2f} seconds.")

    # --- 認証機能 ---
    def authenticate(self):
        AUTH_FILE_PATH = "auth.key"
        
        try:
            with open(AUTH_FILE_PATH, 'r') as f:
                refresh_token = f.read().strip()
        except FileNotFoundError:
            logging.critical(f"🚨 エラー: 認証ファイル '{AUTH_FILE_PATH}' が見つかりません。")
            raise Exception("認証ファイルが見つかりません。")
        
        if not refresh_token:
            logging.critical(f"🚨 エラー: '{AUTH_FILE_PATH}' ファイルが空です。")
            raise Exception("認証ファイルが空です。")

        self.api = AppPixivAPI()
        logging.info("Pixiv API認証中 (Refresh Tokenを使用)...")
        try:
            self.api.auth(refresh_token=refresh_token)
            logging.info("✅ 認証成功")
            return True
        except Exception as e:
            logging.critical(f"❌ 認証失敗: リフレッシュトークンが不正か有効期限切れです。エラー詳細: {e}")
            raise Exception(f"認証失敗: {e}")

    # --- データ取得と計算 ---
    def calculate_engagement(self):
        if not self.api:
            raise Exception("APIが認証されていません。")
            
        mode_str = self.ranking_mode.value 
        content_type_value = self.content_type.value
        
        logging.info(f"--- {mode_str}ランキングの作品データを取得中 (コンテンツ: {content_type_value})... ---")
        
        json_result = self.api.illust_ranking(mode_str) 
        illusts = json_result.illusts
        
        engagement_list = []

        for illust in illusts:
            if content_type_value != 'all' and illust.type != content_type_value:
                continue
            if illust.type == 'ugoira':
                continue
            
            view = illust.total_view
            bookmark = illust.total_bookmarks
            
            if view >= self.min_views_threshold and bookmark >= self.min_bookmarks_threshold:
                engagement_rate = round((bookmark / view) * 100, 2) if view > 0 else 0 
                
                engagement_list.append({
                    'id': illust.id,
                    'title': illust.title,
                    'user_name': illust.user.name,
                    'view': view,
                    'bookmark': bookmark,
                    'rate': engagement_rate
                })
                
        sorted_by_rate = sorted(engagement_list, key=lambda x: x['rate'], reverse=True)
        return sorted_by_rate

    # --- 画像ダウンロード機能 ---
    def download_images(self, sorted_list):
        if not self.api:
            raise Exception("APIが認証されていません。")
        if not sorted_list or not self.enable_download:
            return

        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
            logging.info(f"📁 ダウンロードディレクトリ '{self.download_dir}' を作成しました。")

        # NOTE: print()はGUI側でログにリダイレクトされる
        print(f"\n--- ブックマーク率トップ {self.download_count} 件の画像をダウンロード中 (保存先: {self.download_dir})... ---")
        
        for i, item in enumerate(sorted_list[:self.download_count]):
            # ... (中略: ダウンロードロジックは変更なし) ...
            illust_id = item['id']
            
            rate_str = f"率{item['rate']:.2f}"
            bmark_str = f"ブクマ{self._to_k_unit(item['bookmark'])}"
            view_str = f"閲覧{self._to_k_unit(item['view'])}"
            sanitized_user = self._sanitize_filename(item['user_name'], max_length=15)
            sanitized_title = self._sanitize_filename(item['title'], max_length=30) 
            
            prefix = f"{rate_str}_{bmark_str}_{view_str}_{sanitized_user}_{sanitized_title}"
            
            print(f"ダウンロード開始: {prefix} ({i+1}/{self.download_count})", end='...')
            
            try:
                json_result = self.api.illust_detail(illust_id) 
                illust_object = json_result.illust 

                image_urls = []
                if illust_object.meta_pages:
                    image_urls = [p.image_urls.original for p in illust_object.meta_pages]
                elif illust_object.meta_single_page.original_image_url:
                    image_urls = [illust_object.meta_single_page.original_image_url]
                
            except Exception as e:
                logging.error(f"❌ ID {illust_id} の情報取得中にエラーが発生しました: {e}")
                print(f"\r❌ 情報取得失敗。ログを確認してください。")
                self._rand_sleep() 
                continue
                
            success_count = 0
            
            for idx, url in enumerate(image_urls):
                original_file_name = os.path.basename(url)
                _, ext = os.path.splitext(original_file_name)
                page_num = idx + 1
                page_suffix = f"_p{page_num}" if len(image_urls) > 1 else ""
                final_file_name = f"{prefix}{page_suffix}{ext}"
                
                is_page_downloaded = False
                for attempt in range(3):
                    try:
                        if self.api.download(url, path=self.download_dir, name=final_file_name):
                            success_count += 1
                            is_page_downloaded = True
                            self._rand_sleep()
                            break 
                        else:
                             is_page_downloaded = True 
                             break
                    except Exception as e:
                        logging.warning(f"  [Attempt {attempt+1}] Download {final_file_name} failed: {e}")
                        self._rand_sleep()
                
                if not is_page_downloaded:
                    logging.error(f"❌ 警告: ID {illust_id} のページ{idx+1} ({final_file_name}) は3回の試行でダウンロードできませんでした。")

            if success_count == len(image_urls) and len(image_urls) > 0:
                print(f"\r✅ ダウンロード完了: {prefix} ({success_count}枚)")
            elif len(image_urls) == 0:
                print(f"\r⚠️ ID {illust_id} はダウンロード可能な画像が見つかりませんでした。")
            else:
                print(f"\r⚠️ ダウンロード一部/全体失敗: {prefix} ({success_count}/{len(image_urls)}枚成功)")


# --- ロギング設定 ---

def setup_logging():
    log_file = 'pixiv_analysis.log'
    # ロギング設定の初期化
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8', mode='a'),
            # GUIがない場合はsys.stdoutに流す
            logging.StreamHandler(sys.stdout) 
        ]
    )
    logging.getLogger('pixivpy3').setLevel(logging.INFO)

if __name__ == "__main__":
    # モジュール単体テスト用のコード (通常はGUI側から呼び出すため不要)
    pass