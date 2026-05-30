# ブラウザテスト用シードデータ。callback/validation を回避するため insert_all を使う。
# 25 件: "Ruby" を含むタイトル 12 件 + "Python" を含むタイトル 13 件。
# 検索 "Ruby" -> 12 件 / 1ページ20件なら全25件は2ページ。
Archive.delete_all
now = Time.current
rows = []
12.times do |i|
  rows << { title: format("Ruby Tutorial %02d", i + 1),
            original_url: "https://example.com/ruby/#{i + 1}",
            status: "done", created_at: now - (i * 60), updated_at: now - (i * 60) }
end
13.times do |i|
  rows << { title: format("Python Guide %02d", i + 1),
            original_url: "https://example.com/python/#{i + 1}",
            status: "done", created_at: now - ((i + 12) * 60), updated_at: now - ((i + 12) * 60) }
end
Archive.insert_all(rows)
puts "seeded: #{Archive.count} archives"
