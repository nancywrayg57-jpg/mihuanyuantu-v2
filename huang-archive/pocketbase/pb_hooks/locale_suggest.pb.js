/// <reference path="../pb_data/types.d.ts" />

function mapCountry(c) {
  c = String(c || "").toUpperCase()
  if (!c || c === "XX" || c === "T1") return ""
  if (["CN", "TW", "HK", "MO", "SG"].indexOf(c) >= 0) return "zh"
  if (["RU", "BY", "KZ", "KG", "UZ", "TJ", "AM", "AZ"].indexOf(c) >= 0) return "ru"
  return "en"
}

function fromAcceptLanguage(h) {
  h = String(h || "").toLowerCase()
  if (h.indexOf("zh") >= 0) return "zh"
  if (h.indexOf("ru") >= 0) return "ru"
  if (h.indexOf("en") >= 0) return "en"
  return "zh"
}

routerAdd("GET", "/api/hz/locale-suggest", (c) => {
  try {
    var req = c.request()
    var country =
      req.header.get("CF-IPCountry") ||
      req.header.get("X-Country-Code") ||
      req.header.get("X-Appengine-Country") ||
      ""
    var mapped = mapCountry(country)
    var accept = req.header.get("Accept-Language") || ""
    var locale = mapped || fromAcceptLanguage(accept) || "zh"
    return c.json(200, {
      locale: locale,
      country: String(country || ""),
      source: mapped ? "ip-country" : "accept-language",
    })
  } catch (e) {
    return c.json(200, { locale: "zh", country: "", source: "default" })
  }
})
