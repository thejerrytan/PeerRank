var template = function(data) {
	var expertDiv = $('.twitter-expert').first().html()
	return expertDiv
}

$(document).ready(function() {
	$('#pagination-container').pagination({
		dataSource: function(done){
		    var result = ;
		    for (var i = 1; i < 196; i++) {
		        result.push(i);
		    }
		    done(result);
		},
		pageSize : 10,
		className : 'paginationjs-theme-blue',
		callback: function(data, pagination) {
			var html = Handlebars.compile($('#template-expert').html(), {
            	data: data
        	})
			$('#results-container').html(html)
		}
	})

})
