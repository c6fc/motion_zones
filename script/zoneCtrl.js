angular
   .module('app', [])
   .controller('zoneCtrl', ['$scope', '$http', function($scope, $http) {

      $scope.activeId = 0;
      $scope.zoneId = 1;
      $scope.image = "";
      $scope.imageHeight = 0;
      $scope.imageWidth = 0;
      $scope.activePoint = 1;
      $scope.zones = Array();
      $scope.zone = Array();

      $scope.getZones = function() {
         $http({
            method: 'GET',
            url:    '/zones.json?dx=' + Math.random(),
         }).then(function (response) {
            $scope.zones = response.data.zones;
            $scope.image = response.data.image;
            
            var img = new Image();
            img.onload = function() {
               $scope.imageHeight = this.height;
               $scope.imageWidth = this.width;
               $scope.$apply();
            }
      
            $scope.loadZone(1);
            $scope.image = $scope.image;
            img.src = $scope.image;
            $scope.updatePolygon();
         }, function (response) {
            alert(response);
         });
      }

      // Only one zone can be loaded at a time.      
      $scope.loadZone = function(id) {
         if (typeof $scope.zones[id] != "undefined") {
            $scope.zone = $scope.zones[id];
            $scope.zoneId = id;
            $scope.updatePolygon();
            return true;
         }
         
         return false;
      }
      
      $scope.addZone = function() {
         id = Object.keys($scope.zones).length + 1;
         $scope.zones[id] = {"points":[{"x":100,"y":100},{"x":200,"y":100},{"x":150,"y":200}],"name":"New Zone"}
      }
      
      $scope.deleteZone = function(id) {
         if (Object.keys($scope.zones).length == 1) {
            console.log('Must keep at least 1 zone');
            return false;
         }
         
         oid = id;
         delete $scope.zones[id];
         
         while (typeof $scope.zones[(id * 1 + 1)] != "undefined") {
            $scope.zones[id] = $scope.zones[(id * 1 + 1)];
            delete $scope.zones[(id * 1 + 1)];
            id++;
         }
         
         if (typeof $scope.zones[oid] == "undefined") {
            return $scope.loadZone(oid - 1)
         }
         
         return $scope.loadZone(oid);
      }

      $scope.save = function() {
         console.log(angular.toJson({"zones": $scope.zones, "image": $scope.image}));
      }

      $scope.updatePolygon = function() {
         points = "";
         for (var i in $scope.zone['points']) {
            points += $scope.zone['points'][i]['x'] + "," + $scope.zone['points'][i]['y'] + " ";
         };

         $scope.zonePoints = points;
      }

      $scope.addPointAfter = function(id) {
         points = $scope.zone.points;
         next = (id >= points.length - 1) ? 0 : parseInt(id) + 1;
         console.log(next);

         point = {
            "x": Math.round((points[id]['x'] + points[next]['x']) / 2),
            "y": Math.round((points[id]['y'] + points[next]['y']) / 2)
         }

         console.log(point);

         if (next == 0) {
            $scope.zone['points'][points.length] = point;
         } else {
            $scope.zone['points'].splice(next, 0, point);
         }
      }

      $scope.removePoint = function(id) {
         if ($scope.zone.points.length == 3) {
            alert('Must maintain at least 3 points');
            return false;
         }
         
         $scope.zone.points.splice(id, 1);
         console.log($scope.zone.points);
      }
      
      $scope.showSelected = function(id) {
         $('tr.active').removeClass('active');
         $('circle.active').removeClass('active').addClass('inactive');
         
         $('tr#row-' + id).addClass('active');
         $('circle#circle-' + id).addClass('active').removeClass('inactive');
         
         $scope.activeId = id;
         console.log(id);
      }

      $scope.getZones();
   }])
   .directive('myDraggable', ['$document', function($document) {
      return {
         scope: false,
         link: function(scope, element, attr) {
            var startX = 0, startY = 0, x = 0, y = 0;

            element.css({
               position: 'absolute',
               border: '1px solid red',
               backgroundColor: 'lightgrey',
               cursor: 'pointer'
            });

            element.on('mousedown', function(event) {
               // Prevent default dragging of selected content
               event.preventDefault();
               offsetX = event.pageX - element.attr('cx');
               offsetY = event.pageY - element.attr('cy');
               
               point = element.attr("point");
               scope.activePoint = point;
               console.log(point);
               $document.on('mousemove', mousemove);
               $document.on('mouseup', mouseup);
               scope.$apply();
            });

            function mousemove(event) {
               x = event.pageX - offsetX;
               y = event.pageY - offsetY;

               x = (x < 0) ? 0 : x;
               y = (y < 0) ? 0 : y;
               x = (x > scope.imageWidth) ? scope.imageWidth : x;
               y = (y > scope.imageHeight) ? scope.imageHeight : y;

               scope.zone.points[point]['x'] = x;
               scope.zone.points[point]['y'] = y;
               scope.updatePolygon();
               scope.$apply();
            }

            function mouseup() {
               console.log(scope.activePoint)
               $document.off('mousemove', mousemove);
               $document.off('mouseup', mouseup);
               scope.$apply();
            }
         }
      }
   }]);
