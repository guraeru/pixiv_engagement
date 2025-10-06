@echo off

chcp 65001

echo "(1)開発コンソール (F12) を開き、ネットワーク タブに切り替えます。"
echo "(2)Networkタブに移動して、(Shift + F)を押す。"
echo "(3)検索ボックスに"callback?"を入れます。"
echo "(4)Pixivログインを進めます。"
echo "(5)ログインすると、次のような空白のページとリクエストが表示されます。"
echo "   パラメータの値をのプロンプトにコピーし、キーを押します。"
echo "   https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback?state=...&code=...codepixiv_auth.py"
echo "(6)エンターや更新で検索結果を更新して、code=以降のトークン文字をそのまま貼り付けてください"
echo "(7)refresh_tokenをコピーして、テキストファイルでauth.keyを作成する"
echo "(8)pixivエンゲージメントが利用可能となる、let enjoy!!"

call "%USERPROFILE%\anaconda3\condabin\conda.bat" activate Test001

python ./pixivpy3/pixiv_auth.py login

pause
