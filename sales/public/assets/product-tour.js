/* Marketing media only. Does not contact billing, auth or provider APIs. */
(function () {
  'use strict';
  document.querySelectorAll('[data-bf-tour]').forEach(function (container) {
    var video = container.querySelector('video');
    var play = container.querySelector('[data-tour-play]');
    var status = container.parentElement.querySelector('[data-tour-status]');
    if (!video || !play) return;
    video.muted = true;
    function errorMessage() {
      play.hidden = false;
      if (status) status.textContent = 'This browser could not play the video. Try the animated HTML tour or download the MP4 below.';
    }
    play.addEventListener('click', function () {
      if (status) status.textContent = '';
      if (video.ended) video.currentTime = 0;
      var result = video.play();
      if (result && result.catch) result.catch(errorMessage);
    });
    video.addEventListener('play', function () {
      play.hidden = true;
      document.querySelectorAll('[data-bf-tour] video').forEach(function (other) {
        if (other !== video) other.pause();
      });
    });
    video.addEventListener('ended', function () {
      play.hidden = false;
      play.querySelector('span').textContent = 'Replay the tour';
    });
    video.addEventListener('error', errorMessage);
  });
})();
