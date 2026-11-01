angular.module('deciframeApp').controller('SequenciaController', function($http, $window, ngProgressFactory, $anchorScroll, $location, GENEROS) {
  var COR_SEQUENCIA = '#2E1C74';
  var vm = this;
  vm.sequenciasFamosas = [];
  vm.carregandoSequencias = true;
  vm.erroSequencias = "";
  vm.catalogoVazio = false;
  vm.novaSequencia = "";
  vm.cadastrando = false;
  vm.erroCadastro = "";
  vm.minhaSequencia = {};
  vm.isSearching = false;
  vm.showSearchResultsCount = false;
  vm.esfigeSpeech =  "";
  vm.musics = [];
  vm.generos = GENEROS;
  vm.meuGenero = "";
  vm.progressbar = ngProgressFactory.createInstance();

  var formatarSequencia = function(sequencia) {
    return {
      id: sequencia.id,
      acordes: sequencia.acordes.map(function(acorde) {
        return { 'acorde': acorde, 'cor': COR_SEQUENCIA };
      })
    };
  };

  vm.carregarSequencias = function() {
    vm.carregandoSequencias = true;
    vm.erroSequencias = "";
    vm.catalogoVazio = false;

    $http.get("sequencias")
      .success(function(data) {
        vm.carregandoSequencias = false;
        vm.sequenciasFamosas = data.map(formatarSequencia);
        vm.catalogoVazio = vm.sequenciasFamosas.length === 0;
      })
      .error(function() {
        vm.carregandoSequencias = false;
        vm.sequenciasFamosas = [];
        vm.catalogoVazio = false;
        vm.erroSequencias = "Não foi possível carregar as sequências.";
      });
  };

  vm.carregarSequencias();

  vm.temAcorde = function(acorde) {
    if (vm.minhaSequencia.acordes) {
      return (vm.minhaSequencia.acordes.indexOf(acorde) > -1);
    } else {
      return false;
    }
  }

  var createChordsString = function(chords) {
    var str = "";
    for (var i = 0; i < chords.length; i++) {
      str = str.concat(chords[i].acorde, ',');
    }
    return str.substring(0, str.length-1);
  }

  var validarNovaSequencia = function(tokens) {
    if (tokens.length < 1 || tokens.length > 12) {
      return "Informe entre 1 e 12 acordes.";
    }
    for (var i = 0; i < tokens.length; i++) {
      var token = tokens[i];
      if (token.length > 12) {
        return "Cada acorde pode ter no máximo 12 caracteres.";
      }
      if (/\s/.test(token)) {
        return "Acorde não pode conter espaço.";
      }
      if (/[,;|]/.test(token)) {
        return "Acorde não pode conter , ; ou |.";
      }
    }
    return "";
  };

  vm.cadastrarSequencia = function() {
    var tokens = vm.novaSequencia.split(',').map(function(parte) {
      return parte.trim();
    }).filter(function(token) {
      return token !== "";
    });

    var erro = validarNovaSequencia(tokens);
    if (erro) {
      vm.erroCadastro = erro;
      return;
    }

    vm.cadastrando = true;
    vm.erroCadastro = "";

    $http.post("sequencias", { acordes: tokens })
      .success(function(data) {
        var sequencia = formatarSequencia(data);
        vm.sequenciasFamosas.push(sequencia);
        vm.catalogoVazio = false;
        vm.novaSequencia = "";
        vm.pesquisarPorSequencia(sequencia);
      })
      .error(function(data) {
        if (data && data.erro) {
          if (data.id !== undefined && data.id !== null) {
            vm.erroCadastro = data.erro + " (id " + data.id + ")";
          } else {
            vm.erroCadastro = data.erro;
          }
        } else {
          vm.erroCadastro = "Não foi possível cadastrar a sequência.";
        }
      })
      .finally(function() {
        vm.cadastrando = false;
      });
  };

  vm.pesquisarPorSequencia = function(sequencia) {
    if (sequencia) {
      vm.minhaSequencia = sequencia;
    }
    vm.progressbar.start();
    vm.esfigeSpeech = "Procurando músicas com base na sequencia...";
    vm.isSearching = true;
    vm.musics = [];

    var apiUrl = "";
    var searchString = "similares?sequencia=".concat(createChordsString(vm.minhaSequencia.acordes));
    if (vm.meuGenero !== "" && vm.meuGenero !== null) {
      searchString += "&generos="+vm.meuGenero;
    }
    $http.get(apiUrl.concat(searchString))
      .success(function(data) {
        vm.progressbar.complete();
        vm.esfigeSpeech = "Encontrei essas músicas";
        vm.isSearching = false;
        vm.showSearchResultsCount = true;
        vm.musics = data;
      })
      .error(function(data) {
        vm.esfigeSpeech = "Ops! Algo errado.";
        vm.isSearching = false;
        vm.showSearchResultsCount = false;
      });
  }

  vm.limparPesquisa = function() {
    vm.minhaSequencia = {};
    vm.musics = [];
    vm.showSearchResultsCount = false;
  }

  vm.goToLirics = function(music) {
    $window.open(music.url);
  };

  vm.goToResults = function() {
    vm.showSearchResultsCount = false;
    $("body").animate({scrollTop: $("#results").offset().top}, "slow");
  };
});
