// showing build details
$(document).ready(function () {
  $("table.builds-table tr[class^='build-']").each(function (i, e) {
    $(this).hover(function() { $("table.builds-table tr.details").hide(); $(this).next().show(); });
  });
});
