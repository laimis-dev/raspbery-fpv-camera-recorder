"use strict";

// Rotation is a browser preference; the captured video remains unchanged.
(() => {
  const previewImage = document.getElementById("live-preview");
  const angleSlider = document.getElementById("live-rotation-angle");
  const angleOutput = document.getElementById("live-rotation-value");
  const storageKey = "fpv-live-rotation-degrees";
  let rotationDegrees = 0;
  try {
    const savedDegrees = Number(localStorage.getItem(storageKey));
    if (Number.isFinite(savedDegrees)) rotationDegrees = Math.max(-180, Math.min(180, Math.round(savedDegrees)));
  } catch (_) { /* The controls also work when browser storage is unavailable. */ }

  function fitRotatedPreview() {
    const previewWidth = previewImage.clientWidth;
    const previewHeight = previewImage.clientHeight;
    const imageWidth = previewImage.naturalWidth;
    const imageHeight = previewImage.naturalHeight;
    if (!previewWidth || !previewHeight || !imageWidth || !imageHeight) return;
    const containScale = Math.min(previewWidth / imageWidth, previewHeight / imageHeight);
    const radians = rotationDegrees * Math.PI / 180;
    const rotatedWidth = containScale * (imageWidth * Math.abs(Math.cos(radians)) + imageHeight * Math.abs(Math.sin(radians)));
    const rotatedHeight = containScale * (imageWidth * Math.abs(Math.sin(radians)) + imageHeight * Math.abs(Math.cos(radians)));
    const rotationScale = Math.min(previewWidth / rotatedWidth, previewHeight / rotatedHeight);
    previewImage.style.transform = `rotate(${rotationDegrees}deg) scale(${rotationScale})`;
  }

  function setRotationDegrees(nextDegrees) {
    rotationDegrees = nextDegrees;
    angleSlider.value = String(rotationDegrees);
    angleOutput.value = `${rotationDegrees}°`;
    angleSlider.setAttribute("aria-valuetext", `${rotationDegrees} degrees`);
    fitRotatedPreview();
    try { localStorage.setItem(storageKey, String(rotationDegrees)); } catch (_) { }
  }

  function rotateQuarterTurn(direction) {
    const nextDegrees = rotationDegrees + direction * 90;
    setRotationDegrees(nextDegrees > 180 ? nextDegrees - 360 : nextDegrees < -180 ? nextDegrees + 360 : nextDegrees);
  }

  angleSlider.addEventListener("input", () => setRotationDegrees(Number(angleSlider.value)));
  document.getElementById("rotate-left-button").addEventListener("click", () => rotateQuarterTurn(-1));
  document.getElementById("rotate-right-button").addEventListener("click", () => rotateQuarterTurn(1));
  document.getElementById("reset-rotation-button").addEventListener("click", () => setRotationDegrees(0));
  previewImage.addEventListener("load", fitRotatedPreview);
  new ResizeObserver(fitRotatedPreview).observe(previewImage);
  setRotationDegrees(rotationDegrees);
})();
