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

      /* Keep for eventual database integration

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
      */

      $scope.loadImage = function(event) {
         var img = new Image();
         img.onload = function() {
            $scope.imageHeight = this.height;
            $scope.imageWidth = this.width;
            $scope.$apply();
         }

         img.src = window.URL.createObjectURL(event.target.files[0]);
         $scope.image = img.src
         console.log(img.src)
      }

      $scope.loadJson = function(event) {
         $http({
            method:  'GET',
            url:     window.URL.createObjectURL(event.target.files[0])
         }).then(function(response) {
            $scope.zones = response.data.zones;
            $scope.updateJson();
            $scope.loadZone(1);
         })
      }

      $scope.updateJson = function() {
         for (x in $scope.zones) {
            console.log($scope.zones[x]);
            y = $scope.zones[x];
            y['warmup'] = (typeof y['warmup'] == "undefined") ? 2 : y['warmup'];
            y['cooldown'] = (typeof y['cooldown'] == "undefined") ? 5 : y['cooldown'];
            y['continuation'] = (typeof y['continuation'] == "undefined") ? 3 : y['continuation'];
            y['minimum_x'] = (typeof y['minimum_x'] == "undefined") ? 50 : y['minimum_x'];
            y['minimum_y'] = (typeof y['minimum_y'] == "undefined") ? 50 : y['minimum_y'];
            y['upload_to_s3'] = (typeof y['upload_to_s3'] == "undefined") ? false : y['upload_to_s3'];
            $scope.zones[x] = y;
         }
      }

      $scope.generateBlankZones = function() {
         zones = {
            "1": {
               "points": [
                  {"x":100,"y":100},
                  {"x":200,"y":100},
                  {"x":150,"y":200}
               ],
               "name":           "New Zone",
               "warmup":         2,
               "cooldown":       5,
               "continuation":   3,
               "minimum_x":      50,
               "minimum_y":      50,
               "upload_to_s3":   false,
               "s3_bucket":      ""
            }
         }

         $scope.zones = zones;
         $scope.loadZone(1);
      }

      $scope.downloadZones = function() {
         var element = document.createElement('a');
         element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(angular.toJson({"zones": $scope.zones, "image": $scope.image, "upload_to_s3": $scope.upload_to_s3, "s3_bucket": $scope.s3_bucket})));
         element.setAttribute('download', 'zones.json');
         element.style.display = 'none';

         document.body.appendChild(element);
         element.click();
         document.body.removeChild(element);
      }

      // Only one zone can be loaded at a time.      
      $scope.loadZone = function(id) {
         if (typeof $scope.zones[id] != "undefined") {
            $scope.zone = $scope.zones[id];
            $scope.zoneId = id;

            $scope.min1 = {"x": Math.round(($scope.imageWidth / 2) - ($scope.zone.minimum_x / 2)), "y": Math.round(($scope.imageHeight / 2) - ($scope.zone.minimum_y / 2))};
            $scope.min2 = {"x": Math.round(($scope.imageWidth / 2) + ($scope.zone.minimum_x / 2)), "y": Math.round(($scope.imageHeight / 2) + ($scope.zone.minimum_y / 2))};

            $scope.minPoints = [
               {"x": Math.round(($scope.imageWidth / 2) - ($scope.zone.minimum_x / 2)), "y": Math.round(($scope.imageHeight / 2) - ($scope.zone.minimum_y / 2))},
               {"x": Math.round(($scope.imageWidth / 2) + ($scope.zone.minimum_x / 2)), "y": Math.round(($scope.imageHeight / 2) - ($scope.zone.minimum_y / 2))},
               {"x": Math.round(($scope.imageWidth / 2) + ($scope.zone.minimum_x / 2)), "y": Math.round(($scope.imageHeight / 2) + ($scope.zone.minimum_y / 2))},
               {"x": Math.round(($scope.imageWidth / 2) - ($scope.zone.minimum_x / 2)), "y": Math.round(($scope.imageHeight / 2) + ($scope.zone.minimum_y / 2))}
            ]

            console.log($scope.minPoints);

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

         points = "";
         for (var i in $scope.minPoints) {
            points += $scope.minPoints[i]['x'] + "," + $scope.minPoints[i]['y'] + " ";
         };

         $scope.zoneMinPoints = points;
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

      // $scope.getZones();
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
   }]).directive('minDraggable', ['$document', function($document) {
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

               if (point == 1) {
                  scope.min1 = {"x": x, "y": y}
               } else {
                  scope.min2 = {"x": x, "y": y}
               }

               scope.zones[scope.zoneId].minimum_x = Math.abs(scope.min1['x'] - scope.min2['x']);
               scope.zones[scope.zoneId].minimum_y = Math.abs(scope.min1['y'] - scope.min2['y']);

               scope.minPoints = [
                  {"x": scope.min1['x'], "y": scope.min1['y']},
                  {"x": scope.min2['x'], "y": scope.min1['y']},
                  {"x": scope.min2['x'], "y": scope.min2['y']},
                  {"x": scope.min1['x'], "y": scope.min2['y']}
               ]

               scope.updatePolygon();
               scope.$apply();
            }

            function mouseup() {
               console.log({"min_x": scope.zones[scope.zoneId].minimum_x, "min_y": scope.zones[scope.zoneId].minimum_y})
               $document.off('mousemove', mousemove);
               $document.off('mouseup', mouseup);
               scope.$apply();
            }
         }
      }
   }]);
