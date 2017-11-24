// https://stackoverflow.com/a/10943610/3285282

$(document).ready(function(){
    $.get("https://fedora-copr.github.io/feed.xml", function (data) {

        // https://stackoverflow.com/a/10996297/3285282
        Date.prototype.getMonthName = function() {
            var monthNames = [
                "Jan", "Feb", "Mar", "Apr", "May", "June",
                "July", "Aug", "Sept", "Oct", "Nov", "Dec"
            ];
            return monthNames[this.getMonth()];
        }

        $(data).find("item").each(function () { // or "item" or whatever suits your feed
            var el = $(this);
            var published = new Date(el.find("pubDate").text());
            var f_published = published.getDate() + " " + published.getMonthName() + " " + published.getFullYear()

            $("#blog-title").text(el.find("title").text())
            $("#blog-author").text(el.find("author").text())
            $("#blog-link").attr("href", el.find("link").text())
            $("#blog-date").text(f_published)
            return false
        });
    });
});
