// https://stackoverflow.com/a/10943610/3285282

function show_last_articles(feed_url, count=1){

    $.get(feed_url, function (data) {

        // https://stackoverflow.com/a/10996297/3285282
        Date.prototype.getMonthName = function() {
            var monthNames = [
                "Jan", "Feb", "Mar", "Apr", "May", "June",
                "July", "Aug", "Sept", "Oct", "Nov", "Dec"
            ];
            return monthNames[this.getMonth()];
        }

        $(data).find("item").each(function (index) {
            var el = $(this);
            var published = new Date(el.find("pubDate").text());
            var f_published = published.getDate() + " " + published.getMonthName() + " " + published.getFullYear()

            $("#blog-title-" + index).text(el.find("title").text())
            $("#blog-author-" + index).text(el.find("author").text())
            $("#blog-date-" + index).text(f_published)
            $("#blog-link-" + index).attr("href", el.find("link").text())
            $("#blog-link-" + index).removeClass("hidden")
            if (index == count - 1) {
                return false
            }
        });
    });
};
