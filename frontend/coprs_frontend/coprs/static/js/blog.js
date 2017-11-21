// https://stackoverflow.com/a/10943610/3285282

$(document).ready(function(){
    $.get("https://fedora-copr.github.io/feed.xml", function (data) {
        $(data).find("item").each(function () { // or "item" or whatever suits your feed
            var el = $(this);
            $("#blog-title").text(el.find("title").text())
            $("#blog-author").text(el.find("author").text())
            $("#blog-link").attr("href", el.find("link").text())
            $("#blog-date").text(el.find("pubDate").text().split(" ").slice(0, 4).join(" "))
            return false
        });
    });
});
