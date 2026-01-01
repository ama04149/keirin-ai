# CSVファイルがあるフォルダのパスを指定
$folderPath = "C:\Users\wolfs\Desktop\keirin-ai"

# 出力先ファイル名を指定
$outputFile = "C:\Users\wolfs\Desktop\MergedWithFileName.csv"

# 結果を格納する空の配列
$mergedData = @()

# 指定フォルダ内の各CSVファイルを処理
Get-ChildItem -Path $folderPath -Filter *updated*.csv | ForEach-Object {
    $fileName = $_.Name
    # ファイルの内容をインポート
    $csvData = Import-Csv -Path $_.FullName -Encoding UTF8
    
    # 各行にファイル名を追加
    foreach ($row in $csvData) {
        # 新しいプロパティ 'SourceFileName' を追加し、ファイル名をセット
        $row | Add-Member -MemberType NoteProperty -Name "SourceFileName" -Value $fileName
        $mergedData += $row
    }
}

# 結合したデータを新しいCSVファイルとしてエクスポート
$mergedData | Export-Csv -Path $outputFile -Encoding UTF8 -NoTypeInformation

Write-Host "マージが完了しました: $outputFile"