/** Preset form dropdown options sourced from legacy UI candidates + live value union.
 * Source: 输入材料/旧版可复用模块/02_设备参数/界面候选值.json + 线上预设_脱敏原始.json
 */

export type PresetOption = { value: string; label: string }

function valuesToOptions(values: string[]): PresetOption[] {
  return values.map((value) => ({ value, label: value }))
}

function ensureCurrent(options: PresetOption[], current?: string): PresetOption[] {
  const cur = String(current || '').trim()
  if (!cur) return options
  if (options.some((o) => o.value === cur)) return options
  return [{ value: cur, label: cur }, ...options]
}

const SHARED: Record<string, string[]> = {
  "iso": ["50", "64", "100", "125", "160", "200", "250", "320", "400", "500", "640", "800", "1000", "1250", "1600", "2000", "2500", "3200", "4000", "5000", "6400", "8000", "10000", "12800", "25600", "51200", "102400"],
  "shutter_speed": ["30s", "15s", "8s", "4s", "2s", "1s", "1/2", "1/4", "1/8", "1/15", "1/30", "1/60", "1/90", "1/100", "1/125", "1/160", "1/200", "1/250", "1/320", "1/400", "1/500", "1/640", "1/800", "1/1000", "1/1250", "1/1600", "1/2000", "1/2500", "1/3200", "1/4000", "1/5000", "1/8000"],
  "aperture": ["1.0", "1.2", "1.4", "1.7", "1.8", "2.0", "2.4", "2.8", "3.2", "3.5", "4.0", "4.5", "5.0", "5.6", "6.3", "7.1", "8.0", "9.0", "10", "11", "13", "14", "16", "18", "20", "22", "25", "29", "32"],
  "focal_length": ["1.5", "2.0", "2.8", "3.5", "4.0", "4.5", "5.0", "5.5", "6.0", "6.765", "7.0", "8.0", "10", "12", "14", "16", "18", "20", "24", "28", "35", "50", "55", "70", "85", "100", "105", "135", "150", "200", "300", "400", "500", "600"],
  "focal_length_equiv": ["14", "16", "18", "20", "21", "24", "26", "28", "35", "40", "50", "55", "70", "85", "100", "105", "135", "150", "200", "300", "400", "500", "600"],
  "ev_value": ["-3", "-2.7", "-2.3", "-2", "-1.7", "-1.3", "-1", "-0.7", "-0.3", "0", "0.3", "0.7", "1", "1.3", "1.7", "2", "2.3", "2.7", "3"],
}

const DEVICE_SCOPED: Record<string, Record<string, string[]>> = {
  "phone": {
    "camera_make": ["Apple", "Huawei", "Xiaomi", "OPPO", "vivo", "Samsung", "Google", "OnePlus", "Realme", "Honor", "Motorola", "Sony"],
    "camera_model": ["iPhone 16 Pro Max", "iPhone 16 Pro", "iPhone 15 Pro Max", "iPhone 15 Pro", "iPhone 14 Pro Max", "iPhone 14 Pro", "iPhone 13 Pro", "Pixel 9 Pro", "Pixel 8 Pro", "Galaxy S25 Ultra", "Galaxy S24 Ultra", "Xiaomi 15 Ultra", "Xiaomi 14 Ultra", "P60 Pro", "Mate 60 Pro", "Find X8 Pro", "vivo X200 Pro", "iPhone 16", "iPhone 15", "iPhone 14", "iPhone 13 Pro Max", "iPhone 13", "iPhone 15 Plus", "Pixel 7 Pro", "Pixel 8", "Huawei P60 Pro", "Huawei Mate 60 Pro", "Huawei Mate 60 Pro+", "Huawei P60 Art", "12", "OPPO Find X6 Pro", "OPPO Find X7", "OPPO Find X7 Ultra", "Find X7 Ultra", "Samsung SM-S928B", "Samsung SM-S931B", "Samsung SM-S926B", "Samsung SM-S918B", "Galaxy S24", "Galaxy S23+", "Galaxy Z Fold 5", "Galaxy S24+", "Galaxy S23 Ultra", "X100 Pro", "Xiaomi 14", "Xiaomi 13 Ultra", "Xiaomi 14 Pro", "14 Pro", "14 Ultra"],
    "lens_model": ["内置主摄", "内置超广角", "内置长焦", "内置潜望镜头", "内置微距镜头", "Apple iPhone Camera", "Leica Summicron", "ZEISS Vario-Tessar", "iPhone 15 Pro Max back triple camera 9mm f/2.8", "iPhone 16 back dual wide camera 13mm f/2.2", "iPhone 15 back dual wide camera 6.86mm f/1.6", "iPhone 16 Pro Max back triple camera 6.765mm f/1.78", "iPhone 16 Pro back triple camera 6.765mm f/1.78", "Apple 86mm f/2.6", "Apple 103mm f/2.5", "Apple 41mm f/2.7", "Apple 145mm f/2.4", "Apple 80mm f/2.9", "Apple 17mm f/2.3", "Apple 160mm f/2.7", "Apple 99mm f/2.5", "Apple 85mm f/2.5", "Apple 85mm f/3.8", "Apple 96mm f/2.2", "Apple 59mm f/1.9", "Apple 102mm f/2.7", "Apple 93mm f/3.7", "Apple 94mm f/2.4", "Apple 182mm f/2.7", "Apple 67mm f/1.8", "Apple 69mm f/2.2", "Apple 191mm f/1.9", "Apple 165mm f/2.3", "Apple 34mm f/2.8", "Apple 118mm f/3.3", "Apple 66mm f/2.1", "Apple 187mm f/2.5", "Apple 149mm f/3.2", "Apple 166mm f/2.5", "Apple 192mm f/3.5", "Apple 22mm f/2.6", "Apple 181mm f/2", "Apple 148mm f/2.8", "Apple 163mm f/2.4", "Apple 77mm f/2.4", "Apple 127mm f/2.5", "Apple 64mm f/3.6", "Apple 126mm f/1.9", "Apple 195mm f/2.8", "Apple 57mm f/2.5", "Apple 16mm f/2.3", "Google 66mm f/2.1", "Google 188mm f/2.1", "Google 193mm f/2.5", "Google 169mm f/2.8", "Google 179mm f/2.4", "Google 106mm f/2", "Google 82mm f/2.7", "Google 137mm f/2.4", "Google 81mm f/2", "Google 175mm f/2.1", "Google 79mm f/3", "Google 184mm f/2.2", "Google 142mm f/2.6", "Google 186mm f/2.5", "Google 173mm f/2", "Google 133mm f/3.9", "Google 121mm f/2.7", "Google 176mm f/2.2", "Google 90mm f/1.9", "Google 117mm f/2.1", "Huawei P60 Pro rear camera 6.25mm f/1.4", "Huawei Mate 60 Pro rear camera 5.9mm f/1.4", "Huawei P60 Pro rear camera 90mm f/2.1", "Huawei Mate 60 Pro+ rear camera 1.6mm f/2.2", "Huawei P60 Art rear camera 6.25mm f/1.4", "Huawei 153mm f/2.8", "Huawei 21mm f/2", "OnePlus 87mm f/2.7", "OnePlus 79mm f/2.9", "OnePlus 45mm f/2.5", "OnePlus 135mm f/2.8", "OPPO Find X6 Pro rear camera 23mm f/1.8", "OPPO Find X7 rear camera 12mm f/2.2", "OPPO Find X7 Ultra rear camera 23mm f/1.67", "OPPO Find X7 Ultra rear camera 65mm f/2.6", "OPPO 183mm f/1.9", "OPPO 29mm f/2.3", "OPPO 157mm f/3.6", "OPPO 119mm f/2", "Samsung Galaxy S24 Ultra rear camera 6.3mm f/1.7", "Samsung Galaxy S24 Ultra rear camera 111.1mm f/4.9", "Samsung Galaxy S25 rear camera 6.4mm f/1.8", "Samsung Galaxy S24+ rear camera 10mm f/2.4", "Samsung Galaxy S23 Ultra rear camera 1.7mm f/2.2", "Samsung 53mm f/2.1", "Samsung 163mm f/1.9", "Samsung 20mm f/3.3", "Samsung 194mm f/1.9", "Samsung 25mm f/3.2", "Samsung 115mm f/1.9", "Samsung 40mm f/2.2", "Samsung 31mm f/1.9", "Samsung 33mm f/2.2", "Samsung 99mm f/2.6", "Samsung 83mm f/2", "Samsung 43mm f/2.9", "Samsung 127mm f/2.2", "Samsung 44mm f/2.3", "Samsung 162mm f/2.1", "Samsung 57mm f/2.4", "Samsung 70mm f/4", "Samsung 126mm f/2", "Samsung 88mm f/2.3", "Samsung 84mm f/2.5", "Samsung 198mm f/3.3", "Samsung 51mm f/2.1", "Samsung 141mm f/2.5", "Samsung 113mm f/2.3", "vivo 95mm f/2.7", "vivo 81mm f/3.2", "Xiaomi 14 Ultra rear camera 23mm f/1.63", "Xiaomi 14 Ultra rear camera 75mm f/2.5", "Xiaomi 14 rear camera 23mm f/1.6", "Xiaomi 13 Ultra rear camera 12mm f/1.8", "Xiaomi 14 Pro rear camera 23mm f/1.42", "Xiaomi 74mm f/2.3", "Xiaomi 73mm f/2.7", "Xiaomi 151mm f/2.6", "Xiaomi 82mm f/2.3", "Xiaomi 188mm f/1.9"],
    "sensor_size": ["1/1.28 inch", "1/1.3 inch", "1/1.5 inch", "1/1.56 inch", "1/1.7 inch", "1/2 inch", "1/2.3 inch", "1/2.5 inch", "1 inch", "1/1.5\"", "1/2.55\" (5.6x4.2mm)", "1/1.78\" (7.6x5.7mm)", "1/1.28\" (9.8x7.3mm)", "1/1.9\"", "1/1.28\"", "1/1.65\"", "1/1.56\"", "1/1.7\"", "1/1.31\"", "1/1.32\" (9.5x7.1mm)", "1/2.51\" (5.7x4.3mm)", "1/1.32\"", "1/1.43\"", "1/1.56\" (8.0x6.0mm)", "1\" (13.2x8.8mm)", "1\"", "1/1.3\" (9.6x7.2mm)", "1/2.52\" (5.7x4.3mm)", "1/3.52\" (3.7x2.8mm)", "1/2.0\"", "1/1.3\"", "1/1.49\" (8.3x6.2mm)", "1/1.49\""],
    "sensor_type": ["CMOS BSI Stacked", "CMOS BSI", "CMOS Stacked", "RYYB CMOS", "CMOS", "BSI-CMOS"],
    "stabilization": ["OIS", "OIS + EIS", "EIS", "None"],
    "lens_make": ["Apple", "Google", "Huawei", "OnePlus", "Hasselblad", "OPPO", "Samsung", "vivo", "Xiaomi"],
  },
  "dslr": {
    "camera_make": ["Canon", "Nikon", "Pentax", "Sigma", "Leica", "Sony"],
    "camera_model": ["EOS 5D Mark IV", "EOS 6D Mark II", "EOS 90D", "EOS 850D", "EOS-1D X Mark III", "D850", "D780", "D7500", "D5600", "D3500", "K-1 Mark II", "K-70", "Canon EOS 5D Mark IV", "EOS R7", "EOS R3", "EOS R5", "EOS 1D X Mark III", "EOS R5 Mark II", "EOS R6 Mark II", "EOS R10", "M11", "SL3", "Nikon D850", "Zfc", "Z6 III", "D6", "Z8", "Z7 II", "Z9", "Z5 II", "Z50 II", "A7R V", "A9 III", "A6700", "A7S III", "A1", "A7 IV", "A7R IV", "A7C II"],
    "lens_make": ["Canon", "Nikon", "Sigma", "Tamron", "Zeiss", "Tokina", "Samyang", "Laowa", "Voigtlander", "Leica", "Sony"],
    "lens_model": ["EF 24-70mm f/2.8L II USM", "EF 70-200mm f/2.8L IS III USM", "EF 50mm f/1.2L USM", "EF 85mm f/1.4L IS USM", "EF 16-35mm f/2.8L III USM", "AF-S 24-70mm f/2.8E ED VR", "AF-S 70-200mm f/2.8E FL ED VR", "AF-S 50mm f/1.4G", "AF-S 85mm f/1.4G", "Sigma 50mm f/1.4 Art", "Sigma 35mm f/1.4 Art", "Tamron SP 24-70mm f/2.8 G2", "EF 50mm f/1.8 STM", "EF 35mm f/2 IS USM", "EF 24-70mm f/4L IS USM", "EF 100mm f/2.8L Macro IS USM", "EF 14mm f/2.8L II USM", "RF-S 18-150mm f/3.5-6.3 IS STM", "EF 24-105mm f/4L IS II USM", "RF 70-200mm f/2.8L IS USM", "RF 24-70mm f/2.8L IS USM", "RF 24-105mm f/4L IS USM", "RF-S 18-45mm f/4.5-6.3 IS STM", "EF-S 17-55mm f/2.8 IS USM", "Summilux-M 50mm f/1.4 ASPH", "Vario-Elmarit-SL 24-90mm f/2.8-4 ASPH", "AF-S NIKKOR 70-200mm f/2.8E FL ED VR", "AF-S NIKKOR 24-70mm f/2.8E ED VR", "AF-S Micro NIKKOR 105mm f/2.8G IF-ED VR", "AF-S NIKKOR 50mm f/1.8G", "AF-S NIKKOR 14-24mm f/2.8G ED", "AF-S Micro NIKKOR 60mm f/2.8G ED", "NIKKOR Z DX 16-50mm f/3.5-6.3 VR", "NIKKOR Z 24-70mm f/4 S", "AF-S NIKKOR 24-120mm f/4G ED VR", "NIKKOR Z 24-120mm f/4 S", "NIKKOR Z 24-70mm f/2.8 S", "NIKKOR Z 24-50mm f/4-6.3", "FE 24-105mm f/4 G OSS", "FE 70-200mm f/2.8 GM OSS II", "E 18-135mm f/3.5-5.6 OSS", "FE 24mm f/1.4 GM", "FE 24-70mm f/2.8 GM II", "FE 28-70mm f/3.5-5.6 OSS", "FE 16-35mm f/2.8 GM", "FE 24-50mm f/2.8 G"],
    "sensor_size": ["Full Frame (35mm)", "APS-C", "Medium Format", "Full Frame (36x24mm)", "Full Frame"],
    "sensor_type": ["CMOS", "Dual Pixel CMOS", "CMOS BSI", "CCD", "Foveon X3"],
    "stabilization": ["None", "IS (Canon)", "VR (Nikon)", "IS + IBIS", "Sensor Shift", "IS", "IBIS+OIS", "OIS", "IBIS", "VR"],
  },
  "mirrorless": {
    "camera_make": ["Sony", "Fujifilm", "Canon", "Nikon", "Panasonic", "Olympus", "Leica", "Hasselblad", "Sigma", "OM System"],
    "camera_model": ["A7R V", "A7 IV", "A7C II", "A7CR", "A6700", "ZV-E1", "EOS R5 Mark II", "EOS R6 Mark II", "EOS R8", "EOS R50", "Z9", "Z8", "Z7 II", "Z6 III", "Z5 II", "X-T5", "X-H2S", "X-H2", "X-S20", "GH7", "G9 II", "OM-5", "OM-1 Mark II", "SL3", "X2D 100C", "EOS M50 Mark II", "Fujifilm X-T4", "Fujifilm X100VI", "Fujifilm GFX 100S", "Fujifilm X-S20", "Fujifilm X-T5", "Fujifilm X-H2", "Fujifilm X-H2S", "GFX 100S II", "X100VI", "Leica SL3", "Leica Q3", "Leica M11", "Leica M11-P", "Z30", "OM System OM-1", "OM System OM-5", "OM System OM-1 Mark II", "Panasonic DC-GH6", "Panasonic DC-S1R", "Panasonic DC-S5M2", "Panasonic DC-S1", "Lumix S5 II", "Lumix G9 II", "Sony ILCE-7RM5", "Sony ILCE-7M4", "Sony ILCE-7M3", "Sony ILCE-7SM3", "Sony ILCE-1", "Sony ILCE-7CM2", "Sony ZV-E1"],
    "lens_make": ["Sony", "Canon", "Nikon", "Fujifilm", "Panasonic", "Sigma", "Tamron", "Zeiss", "Voigtlander", "Laowa", "Samyang", "Leica", "OM System"],
    "lens_model": ["FE 24-70mm f/2.8 GM II", "FE 85mm f/1.4 GM", "FE 16-35mm f/2.8 GM", "FE 50mm f/1.2 GM", "FE 70-200mm f/2.8 GM OSS II", "RF 50mm f/1.2L USM", "RF 24-70mm f/2.8L IS USM", "RF 85mm f/1.2L USM", "NIKKOR Z 50mm f/1.2 S", "NIKKOR Z 24-70mm f/2.8 S", "XF 56mm f/1.2 R WR", "XF 23mm f/1.4 R LM WR", "Sigma 50mm f/1.4 Art", "Tamron 28-75mm f/2.8 G2", "EF-M 15-45mm f/3.5-6.3 IS STM", "XF 35mm f/1.4 R", "Fujinon 23mm f/2 WR", "GF 110mm f/2 R LM WR", "XF 18-55mm f/2.8-4 R LM OIS", "XF 80mm f/2.8 R LM OIS WR Macro", "XF 10-24mm f/4 R OIS WR", "XF 150-600mm f/5.6-8 R LM OIS WR", "GF 32-64mm f/4 R LM WR", "XF 16-80mm f/4 R OIS WR", "Fujinon 23mm f/2", "Leica APO-Summicron-SL 50mm f/2 ASPH", "Summilux 28mm f/1.7 ASPH", "Summicron-M 35mm f/2 ASPH", "Vario-Elmarit-SL 16-35mm f/3.5-4.5 ASPH", "Noctilux-M 50mm f/0.95 ASPH", "Summilux-SL 75mm f/1.5 ASPH", "APO-Macro-Elmarit-M 90mm f/2.8", "Super-Vario-Elmarit-SL 16-35mm f/3.5-4.5 ASPH", "NIKKOR Z DX 16-50mm f/3.5-6.3 VR", "M.Zuiko Digital ED 7-14mm f/2.8 PRO", "M.Zuiko Digital ED 45mm f/1.2 PRO", "M.Zuiko Digital ED 40-150mm f/2.8 PRO", "M.Zuiko Digital ED 60mm f/2.8 Macro", "M.Zuiko Digital ED 17mm f/1.2 PRO", "M.Zuiko Digital ED 100-400mm f/5.0-6.3 IS", "M.Zuiko Digital ED 12-45mm f/4 PRO", "M.Zuiko Digital ED 8mm f/1.8 Fisheye PRO", "M.Zuiko Digital ED 25mm f/1.2 PRO", "M.Zuiko 12-40mm f/2.8 PRO II", "M.Zuiko 12-45mm f/4 PRO", "Leica DG Elmarit 200mm f/2.8 Power OIS", "Lumix S PRO 70-200mm f/4 OIS", "Lumix S Macro 24mm f/3.5", "Leica DG Summilux 15mm f/1.7 ASPH", "Lumix S 24-105mm f/4 Macro OIS", "Leica DG Macro-Elmarit 45mm f/2.8 ASPH OIS", "Lumix S 14-28mm f/4-5.6 Macro", "Lumix S PRO 50mm f/1.4", "Lumix S 20-60mm f/3.5-5.6", "Lumix S 50mm f/1.8", "Leica DG 12-60mm f/2.8-4", "FE 50mm f/1.4 GM", "FE 35mm f/1.8", "FE 600mm f/4 GM OSS", "FE 14mm f/1.8 GM", "FE 90mm f/2.8 Macro G OSS", "E 18-135mm f/3.5-5.6 OSS", "FE 24-105mm f/4 G OSS", "FE 20-60mm f/3.5-5.6", "FE 24-50mm f/2.8 G"],
    "sensor_size": ["Full Frame (35mm)", "APS-C", "Micro Four Thirds", "Medium Format", "APS-C (23.5x15.6mm)", "Medium Format (43.8x32.9mm)", "Full Frame (36x24mm)", "Micro Four Thirds (17.4x13mm)", "Full Frame"],
    "sensor_type": ["CMOS BSI Stacked", "CMOS BSI", "CMOS Stacked", "CMOS", "Live MOS", "BSI-CMOS"],
    "stabilization": ["IBIS", "OIS + IBIS", "5-Axis IBIS", "OIS", "None", "IBIS+OIS", "IS", "OSS"],
  },
  "action": {
    "camera_make": ["GoPro", "DJI", "Insta360", "Sony", "Garmin", "AKASO", "Ricoh"],
    "camera_model": ["GoPro HERO13 Black", "GoPro HERO12 Black", "GoPro HERO11 Black", "GoPro HERO10 Black", "DJI Osmo Action 5 Pro", "DJI Osmo Action 4", "DJI Action 2", "Insta360 X4", "Insta360 ONE RS", "Insta360 GO 3S", "Sony FDR-X3000", "RX0 II", "DJI Osmo Action 3", "DJI Pocket 3", "Osmo Action 3", "Osmo Pocket 3", "Osmo Action 4", "VIRB 360", "GoPro MAX", "HERO10 Black", "HERO12 Black", "HERO11 Black Mini", "HERO9 Black", "HERO11 Black", "ONE RS 1-Inch 360", "X4"],
    "lens_model": ["内置广角镜头", "内置超广角镜头", "内置标准镜头", "GoPro Wide Lens", "GoPro Macro Lens", "GoPro Anamorphic Lens", "DJI Osmo Action 4 3.7mm f/2.8", "DJI Osmo Action 3 3.7mm f/2.8", "DJI Pocket 3 3.6mm f/2.0", "DJI HorizonSteady", "DJI Pocket 3", "DJI RockSteady", "Garmin Wide", "GoPro HERO13 Black 2.69mm f/2.8", "GoPro HERO12 Black 2.69mm f/2.8", "GoPro HERO11 Black 2.69mm f/2.8", "GoPro MAX 2.92mm f/2.8", "GoPro SuperView", "GoPro HyperSmooth", "Leica Summicron", "Insta360 FlowState", "ZEISS Tessar T* 24mm f/4"],
    "sensor_size": ["1/1.9 inch", "1/2 inch", "1/2.3 inch", "1/2.5 inch", "1/3 inch", "1/1.3\" (9.6x7.2mm)", "1/1.7\" (7.4x5.6mm)", "1\" (13.2x8.8mm)", "1/1.7\"", "1\"", "1/1.3\"", "1/2.3\"", "1/1.9\" (7.2x5.4mm)", "1/2.3\" (6.2x4.7mm)", "1/1.9\"", "1/2\""],
    "sensor_type": ["CMOS", "CMOS BSI", "CMOS Stacked", "BSI-CMOS"],
    "stabilization": ["EIS", "HorizonSteady (GoPro)", "RockSteady (DJI)", "FlowState (Insta360)", "OIS + EIS", "None", "RockSteady", "ActiveTrack", "HyperSmooth", "FlowState", "HorizonLock"],
    "lens_make": ["DJI", "Garmin", "GoPro", "Insta360", "Sony"],
  },
}

const SELECTS: Record<string, PresetOption[]> = {
  "category": [{"value": "phone", "label": "📱 手机拍摄"}, {"value": "dslr", "label": "📷 单反相机"}, {"value": "mirrorless", "label": "📸 微单相机"}, {"value": "action", "label": "🏃 运动相机"}],
  "white_balance": [{"value": "Auto", "label": "Auto"}, {"value": "Daylight", "label": "Daylight（日光）"}, {"value": "Cloudy", "label": "Cloudy（阴天）"}, {"value": "Tungsten", "label": "Tungsten（鸨丝灯）"}, {"value": "Fluorescent", "label": "Fluorescent（荧光灯）"}, {"value": "Flash", "label": "Flash（闪光灯）"}, {"value": "Shade", "label": "Shade"}],
  "metering_mode": [{"value": "", "label": "--选择--"}, {"value": "Multi-segment", "label": "分区测光"}, {"value": "Center-weighted", "label": "中心测光"}, {"value": "Spot", "label": "点测光"}, {"value": "Matrix", "label": "Matrix"}, {"value": "Pattern", "label": "Pattern"}, {"value": "Evaluative", "label": "Evaluative"}, {"value": "Multi", "label": "Multi"}, {"value": "ESP", "label": "ESP"}],
  "exposure_mode": [{"value": "", "label": "--选择--"}, {"value": "Auto", "label": "全自动"}, {"value": "Aperture Priority", "label": "光圈优先"}, {"value": "Shutter Priority", "label": "快门优先"}, {"value": "Manual", "label": "手动"}, {"value": "Program", "label": "程序自动"}, {"value": "Program AE", "label": "Program AE"}],
  "flash_mode": [{"value": "Off", "label": "关闭"}, {"value": "Auto", "label": "自动"}, {"value": "On", "label": "强制闪光"}, {"value": "Red-eye", "label": "防红眼"}],
  "image_format": [{"value": "JPEG", "label": "JPEG"}, {"value": "HEIC", "label": "HEIC"}, {"value": "RAW", "label": "RAW"}, {"value": "PNG", "label": "PNG"}, {"value": "TIFF", "label": "TIFF"}, {"value": "RAW+JPEG", "label": "RAW+JPEG"}],
  "color_space": [{"value": "sRGB", "label": "sRGB"}, {"value": "Display P3", "label": "Display P3"}, {"value": "AdobeRGB", "label": "Adobe RGB"}, {"value": "ProPhoto RGB", "label": "ProPhoto RGB"}],
  "gps_mode": [{"value": "none", "label": "不写入 GPS"}, {"value": "fixed", "label": "固定坐标（手动填写）"}, {"value": "random_by_scene", "label": "按场景随机生成"}],
  "scene_type": [{"value": "urban", "label": "城市"}, {"value": "landscape", "label": "风景"}, {"value": "beach", "label": "海滩"}, {"value": "mountain", "label": "山地"}, {"value": "street", "label": "街拍"}, {"value": "indoor", "label": "室内"}],
  "maker_note_template": [{"value": "", "label": "自动（根据相机品牌）"}, {"value": "Canon EOS-1D X", "label": "Canon EOS-1D X"}, {"value": "Canon EOS-1D X Mark III", "label": "Canon EOS-1D X Mark III"}, {"value": "Canon EOS 5D Mark IV", "label": "Canon EOS 5D Mark IV"}, {"value": "Canon EOS R5", "label": "Canon EOS R5"}, {"value": "Canon EOS R6 Mark II", "label": "Canon EOS R6 Mark II"}, {"value": "Nikon D850", "label": "Nikon D850"}, {"value": "Nikon D780", "label": "Nikon D780"}, {"value": "Nikon Z7 II", "label": "Nikon Z7 II"}, {"value": "Nikon Z6 II", "label": "Nikon Z6 II"}, {"value": "Sony A7R V", "label": "Sony A7R V"}, {"value": "Sony A7 IV", "label": "Sony A7 IV"}, {"value": "Sony A7 III", "label": "Sony A7 III"}, {"value": "Sony A9 II", "label": "Sony A9 II"}, {"value": "Fujifilm X-T5", "label": "Fujifilm X-T5"}, {"value": "Fujifilm X-T4", "label": "Fujifilm X-T4"}, {"value": "Fujifilm GFX 50S II", "label": "Fujifilm GFX 50S II"}, {"value": "OM System OM-1", "label": "OM System OM-1"}, {"value": "Olympus OM-D E-M1 Mark III", "label": "Olympus OM-D E-M1 Mark III"}, {"value": "Pentax K-1 Mark II", "label": "Pentax K-1 Mark II"}, {"value": "Pentax K-3 Mark III", "label": "Pentax K-3 Mark III"}, {"value": "Apple iPhone 15 Pro", "label": "Apple iPhone 15 Pro"}, {"value": "Apple iPhone 14 Pro", "label": "Apple iPhone 14 Pro"}, {"value": "Apple iPhone 13 Pro", "label": "Apple iPhone 13 Pro"}, {"value": "Panasonic Lumix S5 II", "label": "Panasonic Lumix S5 II"}, {"value": "Panasonic Lumix G9 II", "label": "Panasonic Lumix G9 II"}],
  "shutter_type": [{"value": "-", "label": "-"}, {"value": "EFCS", "label": "EFCS"}, {"value": "Electronic", "label": "Electronic"}, {"value": "Mechanical", "label": "Mechanical"}],
  "scene_mode": [{"value": "城市建筑", "label": "城市建筑"}, {"value": "城市极限", "label": "城市极限"}, {"value": "城市街拍", "label": "城市街拍"}, {"value": "室内人像", "label": "室内人像"}, {"value": "室内拍摄", "label": "室内拍摄"}, {"value": "山地探险", "label": "山地探险"}, {"value": "山地摄影", "label": "山地摄影"}, {"value": "山地运动", "label": "山地运动"}, {"value": "山地风光", "label": "山地风光"}, {"value": "户外探险", "label": "户外探险"}, {"value": "水上运动", "label": "水上运动"}, {"value": "海滩拍摄", "label": "海滩拍摄"}, {"value": "海滩风光", "label": "海滩风光"}, {"value": "街头人文", "label": "街头人文"}, {"value": "街头摄影", "label": "街头摄影"}, {"value": "街头运动", "label": "街头运动"}, {"value": "风景摄影", "label": "风景摄影"}, {"value": "风景旅拍", "label": "风景旅拍"}],
  "color_mode": [{"value": "Flat", "label": "Flat"}, {"value": "Landscape", "label": "Landscape"}, {"value": "Monochrome", "label": "Monochrome"}, {"value": "Natural", "label": "Natural"}, {"value": "Portrait", "label": "Portrait"}, {"value": "Standard", "label": "Standard"}, {"value": "Vivid", "label": "Vivid"}],
  "color_depth": [{"value": "8", "label": "8"}, {"value": "12", "label": "12"}, {"value": "14", "label": "14"}, {"value": "16", "label": "16"}],
  "image_orientation": [{"value": "landscape", "label": "landscape"}, {"value": "portrait", "label": "portrait"}],
  "iso_range": [{"value": "100-102400", "label": "100-102400"}, {"value": "100-3200", "label": "100-3200"}, {"value": "100-51200", "label": "100-51200"}, {"value": "100-6400", "label": "100-6400"}, {"value": "20-3200", "label": "20-3200"}, {"value": "20-6400", "label": "20-6400"}, {"value": "200-25600", "label": "200-25600"}, {"value": "50-204800", "label": "50-204800"}, {"value": "50-50000", "label": "50-50000"}, {"value": "64-102400", "label": "64-102400"}, {"value": "80-51200", "label": "80-51200"}],
  "noise_reduction": [{"value": "0", "label": "0"}, {"value": "1", "label": "1"}, {"value": "2", "label": "2"}, {"value": "3", "label": "3"}, {"value": "4", "label": "4"}, {"value": "5", "label": "5"}, {"value": "6", "label": "6"}, {"value": "7", "label": "7"}, {"value": "8", "label": "8"}, {"value": "9", "label": "9"}, {"value": "10", "label": "10"}, {"value": "11", "label": "11"}, {"value": "12", "label": "12"}, {"value": "13", "label": "13"}, {"value": "14", "label": "14"}, {"value": "15", "label": "15"}, {"value": "16", "label": "16"}, {"value": "17", "label": "17"}, {"value": "18", "label": "18"}, {"value": "19", "label": "19"}, {"value": "20", "label": "20"}, {"value": "21", "label": "21"}, {"value": "22", "label": "22"}, {"value": "23", "label": "23"}, {"value": "24", "label": "24"}, {"value": "25", "label": "25"}, {"value": "26", "label": "26"}, {"value": "27", "label": "27"}, {"value": "28", "label": "28"}, {"value": "29", "label": "29"}, {"value": "30", "label": "30"}, {"value": "31", "label": "31"}, {"value": "32", "label": "32"}, {"value": "33", "label": "33"}, {"value": "34", "label": "34"}, {"value": "35", "label": "35"}, {"value": "36", "label": "36"}, {"value": "37", "label": "37"}, {"value": "38", "label": "38"}, {"value": "39", "label": "39"}],
  "sharpening": [{"value": "0", "label": "0"}, {"value": "1", "label": "1"}, {"value": "2", "label": "2"}, {"value": "3", "label": "3"}, {"value": "4", "label": "4"}, {"value": "5", "label": "5"}, {"value": "6", "label": "6"}, {"value": "7", "label": "7"}, {"value": "8", "label": "8"}, {"value": "9", "label": "9"}, {"value": "10", "label": "10"}, {"value": "11", "label": "11"}, {"value": "12", "label": "12"}, {"value": "13", "label": "13"}, {"value": "14", "label": "14"}, {"value": "15", "label": "15"}, {"value": "16", "label": "16"}, {"value": "17", "label": "17"}, {"value": "18", "label": "18"}, {"value": "19", "label": "19"}, {"value": "20", "label": "20"}, {"value": "21", "label": "21"}, {"value": "22", "label": "22"}, {"value": "23", "label": "23"}, {"value": "24", "label": "24"}, {"value": "25", "label": "25"}, {"value": "26", "label": "26"}, {"value": "27", "label": "27"}, {"value": "28", "label": "28"}, {"value": "29", "label": "29"}, {"value": "30", "label": "30"}, {"value": "31", "label": "31"}, {"value": "32", "label": "32"}, {"value": "33", "label": "33"}, {"value": "34", "label": "34"}, {"value": "35", "label": "35"}, {"value": "36", "label": "36"}, {"value": "37", "label": "37"}, {"value": "38", "label": "38"}, {"value": "39", "label": "39"}],
  "compression_ratio": [{"value": "10", "label": "10"}, {"value": "6", "label": "6"}, {"value": "8", "label": "8"}],
  "software": [{"value": "17.0", "label": "17.0"}, {"value": "18.0", "label": "18.0"}, {"value": "Adobe Lightroom", "label": "Adobe Lightroom"}, {"value": "Adobe Lightroom Classic 13.2", "label": "Adobe Lightroom Classic 13.2"}, {"value": "Adobe Photoshop", "label": "Adobe Photoshop"}, {"value": "Adobe Photoshop 25.5", "label": "Adobe Photoshop 25.5"}, {"value": "Adobe Photoshop Express 13.5", "label": "Adobe Photoshop Express 13.5"}, {"value": "Adobe Premiere Pro 24.2", "label": "Adobe Premiere Pro 24.2"}, {"value": "Affinity Photo 2.4", "label": "Affinity Photo 2.4"}, {"value": "Afterlight 3.2", "label": "Afterlight 3.2"}, {"value": "Camera+ 3.5", "label": "Camera+ 3.5"}, {"value": "CapCut 11.2", "label": "CapCut 11.2"}, {"value": "Capture One 23.4", "label": "Capture One 23.4"}, {"value": "ColorOS 13", "label": "ColorOS 13"}, {"value": "ColorOS 14", "label": "ColorOS 14"}, {"value": "DJI Mimo 1.7", "label": "DJI Mimo 1.7"}, {"value": "DJI Mimo 1.9", "label": "DJI Mimo 1.9"}, {"value": "DJI Mimo 2.0", "label": "DJI Mimo 2.0"}, {"value": "DaVinci Resolve 18.6", "label": "DaVinci Resolve 18.6"}, {"value": "Darkroom 6.8", "label": "Darkroom 6.8"}, {"value": "Darktable 4.6", "label": "Darktable 4.6"}, {"value": "Digital Photo Professional 4.18", "label": "Digital Photo Professional 4.18"}, {"value": "DxO PhotoLab 7.2", "label": "DxO PhotoLab 7.2"}, {"value": "Facetune 2.8", "label": "Facetune 2.8"}, {"value": "Final Cut Pro 10.7", "label": "Final Cut Pro 10.7"}, {"value": "Fujifilm X RAW STUDIO 3.2", "label": "Fujifilm X RAW STUDIO 3.2"}, {"value": "GoPro App 10.0", "label": "GoPro App 10.0"}, {"value": "GoPro App 10.5", "label": "GoPro App 10.5"}, {"value": "GoPro App 9.0", "label": "GoPro App 9.0"}, {"value": "GoPro App 9.5", "label": "GoPro App 9.5"}, {"value": "GoPro Quik 12.3", "label": "GoPro Quik 12.3"}, {"value": "Halide Mark III 2.14", "label": "Halide Mark III 2.14"}, {"value": "HarmonyOS 3.1", "label": "HarmonyOS 3.1"}, {"value": "HarmonyOS 4.0", "label": "HarmonyOS 4.0"}, {"value": "Imaging Edge Desktop 3.5", "label": "Imaging Edge Desktop 3.5"}, {"value": "Insta360 Studio 4.5", "label": "Insta360 Studio 4.5"}, {"value": "Leica FOTOS 4.2", "label": "Leica FOTOS 4.2"}, {"value": "Lightroom Mobile 9.2", "label": "Lightroom Mobile 9.2"}, {"value": "Luminar AI", "label": "Luminar AI"}, {"value": "Luminar Neo 1.18", "label": "Luminar Neo 1.18"}, {"value": "Lumix Tether 1.3", "label": "Lumix Tether 1.3"}, {"value": "MIUI 14", "label": "MIUI 14"}, {"value": "Nikon NX Studio 1.4", "label": "Nikon NX Studio 1.4"}, {"value": "OM Workspace 4.2", "label": "OM Workspace 4.2"}, {"value": "ON1 Photo RAW 2024", "label": "ON1 Photo RAW 2024"}, {"value": "One UI 5.1", "label": "One UI 5.1"}, {"value": "One UI 6.1", "label": "One UI 6.1"}, {"value": "One UI 7.0", "label": "One UI 7.0"}, {"value": "ProCamera 16.3", "label": "ProCamera 16.3"}, {"value": "RawTherapee 5.10", "label": "RawTherapee 5.10"}, {"value": "Snapseed 2.21", "label": "Snapseed 2.21"}, {"value": "VSCO 380", "label": "VSCO 380"}],
  "lens_max_aperture": [{"value": "0.95", "label": "0.95"}, {"value": "1.2", "label": "1.2"}, {"value": "1.4", "label": "1.4"}, {"value": "1.42", "label": "1.42"}, {"value": "1.5", "label": "1.5"}, {"value": "1.6", "label": "1.6"}, {"value": "1.63", "label": "1.63"}, {"value": "1.67", "label": "1.67"}, {"value": "1.7", "label": "1.7"}, {"value": "1.78", "label": "1.78"}, {"value": "1.8", "label": "1.8"}, {"value": "1.9", "label": "1.9"}, {"value": "2", "label": "2"}, {"value": "2.1", "label": "2.1"}, {"value": "2.2", "label": "2.2"}, {"value": "2.3", "label": "2.3"}, {"value": "2.4", "label": "2.4"}, {"value": "2.5", "label": "2.5"}, {"value": "2.6", "label": "2.6"}, {"value": "2.7", "label": "2.7"}, {"value": "2.8", "label": "2.8"}, {"value": "2.9", "label": "2.9"}, {"value": "3", "label": "3"}, {"value": "3.2", "label": "3.2"}, {"value": "3.3", "label": "3.3"}, {"value": "3.5", "label": "3.5"}, {"value": "3.6", "label": "3.6"}, {"value": "3.7", "label": "3.7"}, {"value": "3.8", "label": "3.8"}, {"value": "3.9", "label": "3.9"}, {"value": "4", "label": "4"}, {"value": "4.9", "label": "4.9"}, {"value": "5", "label": "5"}, {"value": "5.6", "label": "5.6"}],
}

const MORE: Record<string, string[]> = {
  "shutter_type": ["-", "EFCS", "Electronic", "Mechanical"],
  "scene_mode": ["城市建筑", "城市极限", "城市街拍", "室内人像", "室内拍摄", "山地探险", "山地摄影", "山地运动", "山地风光", "户外探险", "水上运动", "海滩拍摄", "海滩风光", "街头人文", "街头摄影", "街头运动", "风景摄影", "风景旅拍"],
  "color_mode": ["Flat", "Landscape", "Monochrome", "Natural", "Portrait", "Standard", "Vivid"],
  "color_depth": ["8", "12", "14", "16"],
  "image_orientation": ["landscape", "portrait"],
  "iso_range": ["100-102400", "100-3200", "100-51200", "100-6400", "20-3200", "20-6400", "200-25600", "50-204800", "50-50000", "64-102400", "80-51200"],
  "noise_reduction": ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38", "39"],
  "sharpening": ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38", "39"],
  "compression_ratio": ["10", "6", "8"],
  "software": ["17.0", "18.0", "Adobe Lightroom", "Adobe Lightroom Classic 13.2", "Adobe Photoshop", "Adobe Photoshop 25.5", "Adobe Photoshop Express 13.5", "Adobe Premiere Pro 24.2", "Affinity Photo 2.4", "Afterlight 3.2", "Camera+ 3.5", "CapCut 11.2", "Capture One 23.4", "ColorOS 13", "ColorOS 14", "DJI Mimo 1.7", "DJI Mimo 1.9", "DJI Mimo 2.0", "DaVinci Resolve 18.6", "Darkroom 6.8", "Darktable 4.6", "Digital Photo Professional 4.18", "DxO PhotoLab 7.2", "Facetune 2.8", "Final Cut Pro 10.7", "Fujifilm X RAW STUDIO 3.2", "GoPro App 10.0", "GoPro App 10.5", "GoPro App 9.0", "GoPro App 9.5", "GoPro Quik 12.3", "Halide Mark III 2.14", "HarmonyOS 3.1", "HarmonyOS 4.0", "Imaging Edge Desktop 3.5", "Insta360 Studio 4.5", "Leica FOTOS 4.2", "Lightroom Mobile 9.2", "Luminar AI", "Luminar Neo 1.18", "Lumix Tether 1.3", "MIUI 14", "Nikon NX Studio 1.4", "OM Workspace 4.2", "ON1 Photo RAW 2024", "One UI 5.1", "One UI 6.1", "One UI 7.0", "ProCamera 16.3", "RawTherapee 5.10", "Snapseed 2.21", "VSCO 380"],
  "lens_max_aperture": ["0.95", "1.2", "1.4", "1.42", "1.5", "1.6", "1.63", "1.67", "1.7", "1.78", "1.8", "1.9", "2", "2.1", "2.2", "2.3", "2.4", "2.5", "2.6", "2.7", "2.8", "2.9", "3", "3.2", "3.3", "3.5", "3.6", "3.7", "3.8", "3.9", "4", "4.9", "5", "5.6"],
}

const FIELD_ALIASES: Record<string, string[]> = {
  iso: ['iso'],
  shutter: ['shutter_speed', 'shutter'],
  aperture: ['aperture'],
  focalLength: ['focal_length', 'focalLength'],
  brand: ['camera_make', 'brand'],
  model: ['camera_model', 'model'],
  makerNote: ['maker_note_template', 'makerNote'],
  gpsMode: ['gps_mode', 'gpsMode'],
  deviceType: ['category', 'deviceType'],
}

const DEVICE_FIELDS = new Set([
  'camera_make',
  'camera_model',
  'lens_make',
  'lens_model',
  'sensor_size',
  'sensor_type',
  'stabilization',
  'brand',
  'model',
])

/** Fields that should render as <select> in create/edit form. */
export const PRESET_SELECT_FIELD_KEYS = new Set<string>([
  'deviceType',
  'brand',
  'model',
  'iso',
  'shutter',
  'aperture',
  'focalLength',
  'focal_length_equiv',
  'ev_value',
  'white_balance',
  'metering_mode',
  'exposure_mode',
  'iso_range',
  'shutter_type',
  'lens_make',
  'lens_model',
  'sensor_size',
  'sensor_type',
  'stabilization',
  'lens_max_aperture',
  'flash_mode',
  'image_format',
  'color_space',
  'color_depth',
  'software',
  'image_orientation',
  'compression_ratio',
  'sharpening',
  'noise_reduction',
  'scene_mode',
  'color_mode',
  'gpsMode',
  'scene_type',
  'makerNote',
])

export function optionsForPresetField(
  fieldKey: string,
  deviceType: string,
  currentValue?: string,
): PresetOption[] {
  const keys = FIELD_ALIASES[fieldKey] || [fieldKey]
  let options: PresetOption[] = []

  for (const key of keys) {
    if (SELECTS[key]?.length) {
      options = SELECTS[key]
      break
    }
  }

  if (!options.length) {
    for (const key of keys) {
      if (SHARED[key]?.length) {
        options = valuesToOptions(SHARED[key])
        break
      }
    }
  }

  if (!options.length && MORE[fieldKey]?.length) {
    options = valuesToOptions(MORE[fieldKey])
  }
  if (!options.length) {
    for (const key of keys) {
      if (MORE[key]?.length) {
        options = valuesToOptions(MORE[key])
        break
      }
    }
  }

  const dtype = deviceType && DEVICE_SCOPED[deviceType] ? deviceType : ''
  if (!options.length || DEVICE_FIELDS.has(fieldKey) || keys.some((k) => DEVICE_FIELDS.has(k))) {
    const scopedKeys = keys.flatMap((k) => {
      if (k === 'brand') return ['camera_make']
      if (k === 'model') return ['camera_model']
      return [k]
    })
    for (const key of scopedKeys) {
      const scoped = dtype ? DEVICE_SCOPED[dtype]?.[key] : undefined
      if (scoped?.length) {
        options = valuesToOptions(scoped)
        break
      }
      // union across devices when type missing
      if (!dtype) {
        const union: string[] = []
        const seen = new Set<string>()
        for (const block of Object.values(DEVICE_SCOPED)) {
          for (const v of block[key] || []) {
            if (!seen.has(v)) {
              seen.add(v)
              union.push(v)
            }
          }
        }
        if (union.length) {
          options = valuesToOptions(union)
          break
        }
      }
    }
  }

  // empty placeholder for optional selects
  const withEmpty =
    options.length && options[0]?.value !== ''
      ? [{ value: '', label: '请选择' }, ...options]
      : options
  return ensureCurrent(withEmpty, currentValue)
}
