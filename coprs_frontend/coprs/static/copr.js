// showing build details
$(document).ready(function () {
  $("table.builds-table tr[class^='build-']").each(function (i, e) {
    $(this).hover(function() { $("table.builds-table tr.details").hide(); $(this).next().show(); });
  });
});

// build detail menu arrow slider
$(document).ready(function() {
  $("div.horizontal-menu div a").hover(function() { $(this).toggleClass('pink-arrow'); });
});
