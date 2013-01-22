// showing build details
$(document).ready(function () {
  $("table.builds-table tr[class^='build-']").each(function (i, e) {
    $(this).hover(function() { $("table.builds-table tr.details").hide(); $(this).next().show(); });
  });
});

// build detail menu arrow slider
$(document).ready(function() {
  $("div.horizontal-menu li").hover(
    function() {
      $("div.horizontal-menu li.selected").removeClass('selected').addClass('left-for-now');
      $(this).toggleClass('hovered');
    },
    function() {
      $("div.horizontal-menu li.left-for-now").removeClass('left-for-now').addClass('selected');
      $(this).toggleClass('hovered');
    }
  );
});
