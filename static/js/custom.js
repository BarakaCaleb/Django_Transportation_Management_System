function alert_dialog(text) {
  new duDialog("Error", text, {okText: "Confirm"});
}
function confirm_dialog(title, text, callbacks) {
  new duDialog(
    title, text, {
      buttons: duDialog.OK_CANCEL,
      cancelText: "Cancel",
      okText: "Confirm",
      callbacks: callbacks,
    },
  );
}
function mdtoast_success(text) {
  mdtoast.success(text);
}
function mdtoast_error(text) {
  mdtoast.error(text);
}
function find_datatable_rows_all(datatable_obj) {
  return datatable_obj.rows().nodes().filter(function(row) {
    return $(row).find("input:checkbox");
  }).map($);
}
function find_datatable_rows_clicked(datatable_obj) {
  return datatable_obj.rows().nodes().filter(function(row) {
    return $(row).find("input:checkbox").is(":checked");
  }).map($);
}
$.extend({
  StandardPost: function(url, args){
    let form = $("<form method='post' hidden></form>");
    let input;
    $(document.body).append(form);
    form.attr({"action": url});
    $.each(args, function(key, value) {
      if ($.isArray(value)) {
        input = $("<select type='hidden' multiple></select>");
        input.attr({"name": key});
        value.forEach(function(value_) {
          input.append("<option value=" + value_ + "></option>")
        });
      } else {
        input = $("<input type='hidden'>");
        input.attr({"name": key});
      }
      input.val(value);
      form.append(input);
    });
    form.append(
      $("<input type='hidden' name='csrfmiddlewaretoken' value='" + $("[name='csrfmiddlewaretoken']").val() + "'>")
    );
    form.submit();
    form.remove();
  }
});
$(document).ready(function() {
  duDatepicker(".md-date-picker", {format: 'yyyy-mm-dd', auto: true, i18n: 'zh', maxDate: 'today'});
  mdtimepicker(".md-time-picker", {is24hour: true});
  $(".md-date-picker, .md-time-picker").removeAttr("readonly");
  $(".select2").select2({
    theme: "bootstrap4",
    dropdownCssClass: "text-sm",  // Match body scaling
    width: "style",  // Fix overflow issue
    minimumResultsForSearch: 5,  // Disable search box if less than 5 options
  });
  $(".multiple-select").multipleSelect({
    placeholder: "Unspecified",
    formatSelectAll: function() {return "[Select All]"},
    formatAllSelected: function() {return "All"},
    formatCountSelected: function(count, total) {return "Selected " + count + " items"},
    formatNoMatchesFound: function() {return "None selected"},
  });
  $('[data-widget="pushmenu"]').click(function() {
    Cookies.set("ui_enable_sidebar_collapse", Cookies.get("ui_enable_sidebar_collapse") !== "true");
  });
  // Globally disable form submission by pressing Enter when input is focused, unless the element has "data-allow_enter_submit" attribute
  $(".content-wrapper form input").keypress(function(e) {
    if (e.keyCode === 13 && $(this).attr("data-allow_enter_submit") === undefined) {
      e.preventDefault();
    }
  });
});
