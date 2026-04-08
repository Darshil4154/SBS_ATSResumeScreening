$(document).ready(function() {
    // Initialize DataTable (skip detail rows)
    var table = $('#resultsTable').DataTable({
        paging: false,
        info: false,
        order: [[0, 'asc']],
        columnDefs: [
            { orderable: true, targets: '_all' }
        ]
    });

    // Toggle detail row on click
    $('#resultsTable tbody').on('click', 'tr.candidate-row', function() {
        var id = $(this).data('id');
        var detailRow = $('#detail-' + id);
        if (detailRow.is(':visible')) {
            detailRow.hide();
        } else {
            // Hide all other detail rows
            $('.detail-row').hide();
            detailRow.show();
        }
    });
});
