/* Compteur de segments SMS : même logique que app/services/sms/encoding.py
   (GSM-7 : 160/153, caractères d'extension comptés double ; un seul
   caractère hors alphabet GSM => UCS-2 : 70/67). */
(function () {
  var BASIC = "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?" +
              "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà";
  var EXT = "^{}\\[~]|€\f";

  function analyze(text) {
    var nonGsm = [], length = 0;
    Array.from(text).forEach(function (c) {
      if (BASIC.indexOf(c) === -1 && EXT.indexOf(c) === -1 && nonGsm.indexOf(c) === -1) nonGsm.push(c);
    });
    var single, multi, encoding;
    if (nonGsm.length === 0) {
      Array.from(text).forEach(function (c) { length += EXT.indexOf(c) === -1 ? 1 : 2; });
      single = 160; multi = 153; encoding = "GSM-7";
    } else {
      length = text.length; // unités UTF-16, comme l'UCS-2
      single = 70; multi = 67; encoding = "UCS-2";
    }
    var segments = length === 0 ? 0 : (length <= single ? 1 : Math.ceil(length / multi));
    return { encoding: encoding, length: length, segments: segments, nonGsm: nonGsm };
  }

  window.BaoryxSms = { analyze: analyze };

  document.querySelectorAll("[data-sms-counter]").forEach(function (field) {
    var output = document.getElementById(field.getAttribute("data-sms-counter"));
    if (!output) return;
    function update() {
      var info = analyze(field.value);
      var text = field.value.length + " caractères — " + info.segments + " SMS par destinataire (" + info.encoding + ")";
      if (info.encoding === "UCS-2") {
        text += ". Caractères spéciaux détectés : « " + info.nonGsm.join(" ") +
                " » — le message est limité à 70 caractères par SMS. Remplacez-les (ex. ç → c, ’ → ') pour payer moins.";
      }
      output.textContent = text;
      output.classList.toggle("warning-text", info.encoding === "UCS-2");
    }
    field.addEventListener("input", update);
    update();
  });
})();
