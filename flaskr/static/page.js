// var hostname = '104.196.149.230:5000'
var hostname = 'http://localhost:5000'
Handlebars.registerHelper('ifEq', function(v1, v2, options) {
  if(v1 === v2) {
    return options.fn(this)
  } else {
	  return options.inverse(this)
  }
})

Handlebars.registerHelper('ifOr', function(v1, v2, options) {
	return (v1 || v2) ? options.fn(this) : options.inverse(this)
})


$(document).ready(function () {
	var paginator = $('#pagination-container')
	var expertTemplate = Handlebars.compile($('#template-expert').html())
	var metaTemplate = Handlebars.compile($('#template-meta-data').html())
	var searchExperts = function (queryForm, callback) {
		$.ajax({
	    	url : hostname + '/search',
	    	async: true,
	    	method: 'POST',
	    	dataType : 'json',
	    	data : queryForm.serialize(),
	    	beforeSend: function (jqXHR) {
	    		$("#meta-container").html("<div class='loading'>Fetching results...</div>")
	    		$("#users-container").html("")
	    	},
	    	success: function (response, textStatus, jqXHR) {
	    		// console.log(response)
	    		response.time_taken = response.time_taken.toFixed(2)
	    		var html = metaTemplate(response)
	    		$('#meta-container').html(html)
	    		return callback(response)
	    	},
	    	error: function(jqXHR, textStatus, error) {
	    		$("#results-container").html("<div class='alert alert-danger' role='alert'>There has been an error serving your request. Please try again!</div>")
	    		console.log(error)
	    	},
	    	complete: function(jqXHR, textStatus) {
	    	
	    	}
	    })
	}
	var initPaginator = function (response) {
		paginator.pagination({
			dataSource: response.results,
			hideWhenLessThanOnePage: true,
			pageSize : 10,
			className : 'paginationjs-theme-blue',
			callback: function(data, pagination) {
				var html = ""
				for(var i = 0; i < data.length; i++) {
					html += expertTemplate({
		            	user: data[i]
		        	})
				}
				$('#users-container').html(html)
			}
		})
	}
	var queryForm = $("#query-form")
	queryForm.submit(function (event) {
		event.preventDefault()
		searchExperts(queryForm, initPaginator)
	})
})
