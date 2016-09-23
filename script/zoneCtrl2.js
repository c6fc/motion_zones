angular
   .module('app', [])
   .controller('zoneCtrl', ['$scope', '$http', '$document', function($scope, $http, $document) {

      $scope.imageHeight = 0;
      $scope.imageWidth = 0;
      $scope.activePoint = 1;
      $scope.zone = Array();

      // Only one zone can be loaded at a time.
      $scope.loadZone = function(id) {
         $http({
            method: 'GET',
            url:    '/zone' + id + '.json'
         }).then(function (response) {
            $scope.zone = response.data;
            
            var img = new Image();
            img.onload = function() {
               $scope.imageHeight = this.height;
               $scope.imageWidth = this.width;
               $scope.$apply();
            }
      
            img.src = $scope.zone['image'];
            $scope.updatePolygon();       
         }, function (response) {
            alert(response);
         });
      }

      $scope.report = function() {
         console.log($scope.createBindings());
      }

      $scope.updatePolygon = function() {
         points = "";
         for (var i in $scope.zone['points']) {
            points += $scope.zone['points'][i]['x'] + "," + $scope.zone['points'][i]['y'] + " ";
         };

         $scope.zonePoints = points;
      }

      $scope.mousemove = function(event) {
         x = event.pageX - offsetX;
         y = event.pageY - offsetY;

         x = (x < 0) ? 0 : x;
         y = (y < 0) ? 0 : y;
         x = (x > $scope.imageWidth) ? $scope.imageWidth : x;
         y = (y > $scope.imageHeight) ? $scope.imageHeight : y;

         $scope.zone.points[point]['x'] = x;
         $scope.zone.points[point]['y'] = y;
         $scope.updatePolygon();
      }

      $scope.mouseup = function() {
         $document.off('mousemove', mousemove);
         $document.off('mouseup', mouseup);
      }

      $scope.createBindings = function() {
         for (e = 0; e < angular.element(document).find('circle').length; e++) {
            element = angular.element(angular.element(document).find('circle')[e]);
            console.log(element);

            element.css({
               position: 'absolute',
               cursor: 'pointer'
            });

            element.on('mousedown', function(event) {
               // Prevent default dragging of selected content
               event.preventDefault();
               offsetX = event.pageX - element.attr('cx');
               offsetY = event.pageY - element.attr('cy');
               
               point = element.attr("point");
               $scope.activePoint = point;
               $document.on('mousemove', $scope.mousemove());
               $document.on('mouseup', $scope.mouseup());
            });
         }
      }

      $scope.loadZone(1);
   }]);