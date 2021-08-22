//hide build details
$(document).ready(function () {
  $("table.builds-table tr.details").hide();
});

// showing build details
$(document).ready(function () {
  $("table.builds-table tr[class^='build-']").each(function (i, e) {
    $(this).click(function() { $("table.builds-table tr.details").hide(); $(this).next().show(); });
  });
});

// build detail menu arrow slider
$(document).ready(function() {
  $("div.horizontal-menu li").click(
    function() {
      $("div.horizontal-menu li.selected").removeClass('selected').addClass('left-for-now');
      $(this).toggleClass('clicked');
    },
    function() {
      $("div.horizontal-menu li.left-for-now").removeClass('left-for-now').addClass('selected');
      $(this).toggleClass('clicked');
    }
  );
});

// admin legal-flag divs rolling
$(document).ready(function() {
  $("div.legal-flag").mouseenter(
    function() {
      $(this).children(".message").show("fast");
    }
  );
});

function search_by_attribute(attribute, form_id) {
  event.preventDefault();
  var value = $("form[id=" + form_id + "]").find("input[name=fulltext").val()

  // When searching by group but omitting the starting @
  var group = $(event.target).attr("id") == "search-groupname"
  if (group && value[0] != "@") {
    value = "@" + value
  }

  var url = "/coprs/fulltext/?" + attribute + "=" + value
  window.location.href = url
}
