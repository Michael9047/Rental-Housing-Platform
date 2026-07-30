# 新加坡 NPC 犯罪数据（2024 年度，来源 data.gov.sg）
# 数据刷新: python scripts/fetch_sg_crime.py

SG_CRIME_RECORDS: dict[str, dict[str, int]] = {
  "Central Police Division - Total": {
    "Housebreaking": 17,
    "Snatch Theft": 3,
    "Theft Of Motor Vehicle": 5,
    "Outrage Of Modesty": 238
  },
  "Central Police Division - Bukit Merah East NPC": {
    "Housebreaking": 1,
    "Snatch Theft": 1,
    "Theft Of Motor Vehicle": 2,
    "Outrage Of Modesty": 49
  },
  "Central Police Division - Marina Bay NPC": {
    "Housebreaking": 11,
    "Outrage Of Modesty": 126
  },
  "Central Police Division - Rochor NPC": {
    "Housebreaking": 5,
    "Snatch Theft": 2,
    "Theft Of Motor Vehicle": 3,
    "Outrage Of Modesty": 60
  },
  "Clementi Police Division - Total": {
    "Robbery": 1,
    "Housebreaking": 17,
    "Snatch Theft": 1,
    "Theft Of Motor Vehicle": 13,
    "Outrage Of Modesty": 175
  },
  "Clementi Police Division - Bukit Merah West NPC": {
    "Housebreaking": 3,
    "Snatch Theft": 1,
    "Theft Of Motor Vehicle": 5,
    "Outrage Of Modesty": 46
  },
  "Clementi Police Division - Clementi NPC": {
    "Housebreaking": 4,
    "Theft Of Motor Vehicle": 2,
    "Outrage Of Modesty": 26
  },
  "Clementi Police Division - Jurong East NPC": {
    "Housebreaking": 2,
    "Theft Of Motor Vehicle": 3,
    "Outrage Of Modesty": 45
  },
  "Clementi Police Division - Queenstown NPC": {
    "Robbery": 1,
    "Housebreaking": 8,
    "Theft Of Motor Vehicle": 3,
    "Outrage Of Modesty": 58
  },
  "Tanglin Police Division - Total": {
    "Robbery": 3,
    "Housebreaking": 13,
    "Snatch Theft": 1,
    "Theft Of Motor Vehicle": 7,
    "Outrage Of Modesty": 227
  },
  "Tanglin Police Division - Bishan NPC": {
    "Housebreaking": 3,
    "Theft Of Motor Vehicle": 1,
    "Outrage Of Modesty": 22
  },
  "Tanglin Police Division - Bukit Timah NPC": {
    "Housebreaking": 2,
    "Theft Of Motor Vehicle": 1,
    "Outrage Of Modesty": 20
  },
  "Tanglin Police Division - Kampong Java NPC": {
    "Robbery": 1,
    "Housebreaking": 2,
    "Theft Of Motor Vehicle": 3,
    "Outrage Of Modesty": 27
  },
  "Tanglin Police Division - Orchard NPC": {
    "Robbery": 1,
    "Housebreaking": 6,
    "Snatch Theft": 1,
    "Theft Of Motor Vehicle": 1,
    "Outrage Of Modesty": 125
  },
  "Tanglin Police Division - Toa Payoh NPC": {
    "Robbery": 1,
    "Theft Of Motor Vehicle": 1,
    "Outrage Of Modesty": 32
  },
  "Ang Mo Kio Police Division - Total": {
    "Robbery": 4,
    "Housebreaking": 17,
    "Theft Of Motor Vehicle": 18,
    "Outrage Of Modesty": 218
  },
  "Ang Mo Kio Police Division - Ang Mo Kio North NPC": {
    "Robbery": 1,
    "Housebreaking": 1,
    "Theft Of Motor Vehicle": 1,
    "Outrage Of Modesty": 15
  },
  "Ang Mo Kio Police Division - Ang Mo Kio South NPC": {
    "Housebreaking": 2,
    "Outrage Of Modesty": 13
  },
  "Ang Mo Kio Police Division - Hougang NPC": {
    "Robbery": 1,
    "Housebreaking": 1,
    "Theft Of Motor Vehicle": 1,
    "Outrage Of Modesty": 22
  },
  "Ang Mo Kio Police Division - Punggol NPC": {
    "Robbery": 1,
    "Housebreaking": 4,
    "Theft Of Motor Vehicle": 6,
    "Outrage Of Modesty": 45
  },
  "Ang Mo Kio Police Division - Sengkang NPC": {
    "Housebreaking": 3,
    "Theft Of Motor Vehicle": 6,
    "Outrage Of Modesty": 58
  },
  "Ang Mo Kio Police Division - Serangoon NPC": {
    "Housebreaking": 4,
    "Outrage Of Modesty": 28
  },
  "Ang Mo Kio Police Division - Woodleigh NPC": {
    "Robbery": 1,
    "Housebreaking": 2,
    "Theft Of Motor Vehicle": 4,
    "Outrage Of Modesty": 33
  },
  "Bedok Police Division - Total": {
    "Robbery": 8,
    "Housebreaking": 24,
    "Snatch Theft": 3,
    "Theft Of Motor Vehicle": 9,
    "Outrage Of Modesty": 219
  },
  "Bedok Police Division - Bedok NPC": {
    "Robbery": 1,
    "Housebreaking": 8,
    "Snatch Theft": 1,
    "Theft Of Motor Vehicle": 3,
    "Outrage Of Modesty": 42
  },
  "Bedok Police Division - Changi NPC": {
    "Housebreaking": 3,
    "Outrage Of Modesty": 30
  },
  "Bedok Police Division - Geylang NPC": {
    "Robbery": 2,
    "Housebreaking": 6,
    "Snatch Theft": 1,
    "Theft Of Motor Vehicle": 3,
    "Outrage Of Modesty": 63
  },
  "Bedok Police Division - Marine Parade NPC": {
    "Robbery": 1,
    "Housebreaking": 1,
    "Snatch Theft": 1,
    "Outrage Of Modesty": 32
  },
  "Bedok Police Division - Pasir Ris NPC": {
    "Robbery": 2,
    "Housebreaking": 3,
    "Theft Of Motor Vehicle": 1,
    "Outrage Of Modesty": 18
  },
  "Bedok Police Division - Tampines NPC": {
    "Robbery": 2,
    "Housebreaking": 3,
    "Theft Of Motor Vehicle": 2,
    "Outrage Of Modesty": 27
  },
  "Jurong Police Division - Total": {
    "Robbery": 3,
    "Housebreaking": 18,
    "Snatch Theft": 3,
    "Theft Of Motor Vehicle": 21,
    "Outrage Of Modesty": 219
  },
  "Jurong Police Division - Bukit Batok NPC": {
    "Housebreaking": 6,
    "Snatch Theft": 1,
    "Theft Of Motor Vehicle": 2,
    "Outrage Of Modesty": 51
  },
  "Jurong Police Division - Bukit Panjang NPC": {
    "Housebreaking": 1,
    "Theft Of Motor Vehicle": 2,
    "Outrage Of Modesty": 33
  },
  "Jurong Police Division - Choa Chu Kang NPC": {
    "Robbery": 1,
    "Snatch Theft": 1,
    "Theft Of Motor Vehicle": 9,
    "Outrage Of Modesty": 43
  },
  "Jurong Police Division - Jurong West NPC": {
    "Housebreaking": 8,
    "Theft Of Motor Vehicle": 3,
    "Outrage Of Modesty": 45
  },
  "Jurong Police Division - Nanyang NPC": {
    "Robbery": 2,
    "Housebreaking": 3,
    "Snatch Theft": 1,
    "Theft Of Motor Vehicle": 5,
    "Outrage Of Modesty": 44
  },
  "Woodlands Police Division - Total": {
    "Robbery": 1,
    "Housebreaking": 12,
    "Theft Of Motor Vehicle": 8,
    "Outrage Of Modesty": 122
  },
  "Woodlands Police Division - Woodlands East NPC": {
    "Housebreaking": 3,
    "Outrage Of Modesty": 36
  },
  "Woodlands Police Division - Woodlands West NPC": {
    "Housebreaking": 2,
    "Theft Of Motor Vehicle": 4,
    "Outrage Of Modesty": 28
  },
  "Woodlands Police Division - Yishun North NPC": {
    "Robbery": 1,
    "Housebreaking": 3,
    "Theft Of Motor Vehicle": 1,
    "Outrage Of Modesty": 27
  },
  "Woodlands Police Division - Yishun South NPC": {
    "Housebreaking": 2,
    "Theft Of Motor Vehicle": 1,
    "Outrage Of Modesty": 13
  },
  "Woodlands Police Division - Yishun NPC": {
    "Outrage Of Modesty": 3
  },
  "Woodlands Police Division - Sembawang NPC": {
    "Housebreaking": 2,
    "Theft Of Motor Vehicle": 2,
    "Outrage Of Modesty": 15
  }
}

SG_UML_RECORDS: dict[str, dict[str, int]] = {
  "Central Police Division - Total": {
    "Unlicensed Moneylending": 20,
    "Harassment": 117
  },
  "Central Police Division - Bukit Merah East NPC": {
    "Unlicensed Moneylending": 13,
    "Harassment": 47
  },
  "Central Police Division - Marina Bay NPC": {
    "Unlicensed Moneylending": 3,
    "Harassment": 14
  },
  "Central Police Division - Rochor NPC": {
    "Unlicensed Moneylending": 4,
    "Harassment": 56
  },
  "Clementi Police Division - Total": {
    "Unlicensed Moneylending": 17,
    "Harassment": 387
  },
  "Clementi Police Division - Bukit Merah West NPC": {
    "Unlicensed Moneylending": 4,
    "Harassment": 71
  },
  "Clementi Police Division - Clementi NPC": {
    "Unlicensed Moneylending": 4,
    "Harassment": 106
  },
  "Clementi Police Division - Jurong East NPC": {
    "Unlicensed Moneylending": 2,
    "Harassment": 103
  },
  "Clementi Police Division - Queenstown NPC": {
    "Unlicensed Moneylending": 7,
    "Harassment": 107
  },
  "Tanglin Police Division - Total": {
    "Unlicensed Moneylending": 72,
    "Harassment": 427
  },
  "Tanglin Police Division - Bishan NPC": {
    "Unlicensed Moneylending": 8,
    "Harassment": 76
  },
  "Tanglin Police Division - Bukit Timah NPC": {
    "Unlicensed Moneylending": 20,
    "Harassment": 105
  },
  "Tanglin Police Division - Kampong Java NPC": {
    "Unlicensed Moneylending": 12,
    "Harassment": 82
  },
  "Tanglin Police Division - Orchard NPC": {
    "Unlicensed Moneylending": 12,
    "Harassment": 61
  },
  "Tanglin Police Division - Toa Payoh NPC": {
    "Unlicensed Moneylending": 20,
    "Harassment": 103
  },
  "Ang Mo Kio Police Division - Total": {
    "Unlicensed Moneylending": 50,
    "Harassment": 742
  },
  "Ang Mo Kio Police Division - Ang Mo Kio North NPC": {
    "Unlicensed Moneylending": 5,
    "Harassment": 92
  },
  "Ang Mo Kio Police Division - Ang Mo Kio South NPC": {
    "Unlicensed Moneylending": 6,
    "Harassment": 54
  },
  "Ang Mo Kio Police Division - Hougang NPC": {
    "Unlicensed Moneylending": 8,
    "Harassment": 111
  },
  "Ang Mo Kio Police Division - Punggol NPC": {
    "Unlicensed Moneylending": 6,
    "Harassment": 138
  },
  "Ang Mo Kio Police Division - Sengkang NPC": {
    "Unlicensed Moneylending": 10,
    "Harassment": 175
  },
  "Ang Mo Kio Police Division - Serangoon NPC": {
    "Unlicensed Moneylending": 7,
    "Harassment": 91
  },
  "Ang Mo Kio Police Division - Woodleigh NPC": {
    "Unlicensed Moneylending": 8,
    "Harassment": 81
  },
  "Bedok Police Division - Total": {
    "Unlicensed Moneylending": 83,
    "Harassment": 630
  },
  "Bedok Police Division - Bedok NPC": {
    "Unlicensed Moneylending": 23,
    "Harassment": 231
  },
  "Bedok Police Division - Changi NPC": {
    "Unlicensed Moneylending": 4,
    "Harassment": 94
  },
  "Bedok Police Division - Geylang NPC": {
    "Unlicensed Moneylending": 18,
    "Harassment": 103
  },
  "Bedok Police Division - Marine Parade NPC": {
    "Unlicensed Moneylending": 10,
    "Harassment": 63
  },
  "Bedok Police Division - Pasir Ris NPC": {
    "Unlicensed Moneylending": 12,
    "Harassment": 83
  },
  "Bedok Police Division - Tampines NPC": {
    "Unlicensed Moneylending": 16,
    "Harassment": 56
  },
  "Jurong Police Division - Total": {
    "Unlicensed Moneylending": 64,
    "Harassment": 726
  },
  "Jurong Police Division - Bukit Batok NPC": {
    "Unlicensed Moneylending": 11,
    "Harassment": 145
  },
  "Jurong Police Division - Bukit Panjang NPC": {
    "Unlicensed Moneylending": 6,
    "Harassment": 122
  },
  "Jurong Police Division - Choa Chu Kang NPC": {
    "Unlicensed Moneylending": 17,
    "Harassment": 148
  },
  "Jurong Police Division - Jurong West NPC": {
    "Unlicensed Moneylending": 12,
    "Harassment": 167
  },
  "Jurong Police Division - Nanyang NPC": {
    "Unlicensed Moneylending": 18,
    "Harassment": 144
  },
  "Woodlands Police Division - Total": {
    "Unlicensed Moneylending": 61,
    "Harassment": 438
  },
  "Woodlands Police Division - Woodlands East NPC": {
    "Unlicensed Moneylending": 18,
    "Harassment": 81
  },
  "Woodlands Police Division - Woodlands West NPC": {
    "Unlicensed Moneylending": 17,
    "Harassment": 73
  },
  "Woodlands Police Division - Yishun North NPC": {
    "Unlicensed Moneylending": 13,
    "Harassment": 133
  },
  "Woodlands Police Division - Yishun South NPC": {
    "Unlicensed Moneylending": 5,
    "Harassment": 40
  },
  "Woodlands Police Division - Yishun NPC": {
    "Harassment": 1
  },
  "Woodlands Police Division - Sembawang NPC": {
    "Unlicensed Moneylending": 8,
    "Harassment": 110
  }
}

# NPC 中心坐标（用于最近邻匹配）
SG_NPC_CENTERS: dict[str, tuple[float, float]] = {

    "Ang Mo Kio Police Division - Ang Mo Kio North NPC": (1.375, 103.847),
    "Ang Mo Kio Police Division - Ang Mo Kio South NPC": (1.363, 103.845),
    "Ang Mo Kio Police Division - Hougang NPC": (1.3716, 103.893),
    "Ang Mo Kio Police Division - Punggol NPC": (1.401, 103.9075),
    "Ang Mo Kio Police Division - Sengkang NPC": (1.3906, 103.89),
    "Ang Mo Kio Police Division - Serangoon NPC": (1.3516, 103.871),
    "Ang Mo Kio Police Division - Woodleigh NPC": (1.339, 103.871),
    "Bedok Police Division - Bedok NPC": (1.3236, 103.9303),
    "Bedok Police Division - Changi NPC": (1.343, 103.962),
    "Bedok Police Division - Geylang NPC": (1.3179, 103.8874),
    "Bedok Police Division - Marine Parade NPC": (1.303, 103.908),
    "Bedok Police Division - Pasir Ris NPC": (1.3739, 103.9523),
    "Bedok Police Division - Tampines NPC": (1.3531, 103.9443),
    "Central Police Division - Bukit Merah East NPC": (1.2821, 103.8266),
    "Central Police Division - Marina Bay NPC": (1.2806, 103.857),
    "Central Police Division - Rochor NPC": (1.304, 103.853),
    "Clementi Police Division - Bukit Merah West NPC": (1.285, 103.815),
    "Clementi Police Division - Clementi NPC": (1.3152, 103.7648),
    "Clementi Police Division - Jurong East NPC": (1.3329, 103.7436),
    "Clementi Police Division - Queenstown NPC": (1.294, 103.8),
    "Jurong Police Division - Bukit Batok NPC": (1.3491, 103.7496),
    "Jurong Police Division - Bukit Panjang NPC": (1.3786, 103.7625),
    "Jurong Police Division - Choa Chu Kang NPC": (1.384, 103.744),
    "Jurong Police Division - Jurong West NPC": (1.3404, 103.7065),
    "Jurong Police Division - Nanyang NPC": (1.348, 103.683),
    "Tanglin Police Division - Bishan NPC": (1.3509, 103.8488),
    "Tanglin Police Division - Bukit Timah NPC": (1.3294, 103.8021),
    "Tanglin Police Division - Kampong Java NPC": (1.31, 103.845),
    "Tanglin Police Division - Orchard NPC": (1.3048, 103.8318),
    "Tanglin Police Division - Toa Payoh NPC": (1.3343, 103.8563),
    "Woodlands Police Division - Sembawang NPC": (1.451, 103.821),
    "Woodlands Police Division - Woodlands East NPC": (1.442, 103.796),
    "Woodlands Police Division - Woodlands West NPC": (1.433, 103.775),
    "Woodlands Police Division - Yishun NPC": (1.43, 103.835),
    "Woodlands Police Division - Yishun North NPC": (1.436, 103.835),
    "Woodlands Police Division - Yishun South NPC": (1.425, 103.835),

}
