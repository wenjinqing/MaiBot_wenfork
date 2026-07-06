# 浣跨敤璇存槑
鍙戦€丅绔欒棰戦摼鎺ュ埌缇ら噷锛岄害楹︿細鑷姩瑙ｆ瀽骞跺彂閫佽棰戙€?
瑙夊緱濂界敤鐨勮瘽锛屽彲浠ョ偣涓猻tar
### 璇峰姟蹇呰鐪熷～鍐檆onfig.toml锛侊紒锛侊紒锛?
### 濡傛灉浣犱笉鐭ラ亾浠€涔堟槸wsl锛岃鍔″繀淇濊瘉wsl杞崲涓篺alse锛侊紒锛?
## 浣跨敤鏂规硶

1. 涓嬭浇鏈彃浠躲€?
2. 灏嗘彃浠惰В鍘嬪埌楹﹂害鐨?`plugins` 鐩綍銆?
3. 涓嬭浇 [ffmpeg](https://ffmpeg.org/)銆傦紙涓嶈涓嬭浇婧愪唬鐮侊紒锛侊紒涓媁indows鐗堝晩锛屽埆鎷跨潃婧愪唬鐮佹潵鎵炬垜璇翠綘涓轰粈涔堢敤涓嶄簡锛?
4. 瑙ｅ帇 ffmpeg銆?
5. 灏嗚В鍘嬪悗鐨?ffmpeg 鏂囦欢澶规斁鍒?`bilibili_video_sender_plugin` 鐩綍涓嬨€?
6. 鍏堣繍琛屼竴娆￠害楹︾敓鎴恈onfig.toml銆傚啀鎵撳紑 `config.toml`锛屽～鍏?`sessdata` 鍜?`buvid3`锛堣幏鍙栨柟娉曡涓嬫柟锛夈€?
7. 鍦╪apcat涓婃柊寤轰竴涓鍚慼ttp锛堟湇鍔″櫒锛?骞跺湪config.toml鍐呭～鍏ョ鍙?
8. 浣跨敤鎰夊揩 馃槉銆?

## 娓呮櫚搴﹁缃紙config.toml锛?

鍦?`[bilibili]` 娈?

```toml
[bilibili]
qn = 0
qn_strict = false
```

- `qn=0` 涓鸿嚜鍔細鏈?SESSDATA 榛樿璇锋眰 720P锛屾棤 SESSDATA 榛樿璇锋眰 480P
- `qn_strict=true` 鏃舵竻鏅板害涓嶅彲鐢ㄤ細鐩存帴鎶ラ敊锛堥粯璁よ嚜鍔ㄩ檷绾э級

甯歌 `qn` 瀵瑰簲琛細
- 16 = 360P, 32 = 480P, 64 = 720P, 74 = 720P60, 80 = 1080P, 112 = 1080P+
- 116 = 1080P60, 120 = 4K, 125 = HDR, 126 = 鏉滄瘮瑙嗙晫, 127 = 8K

### URL 鍙傛暟瑕嗙洊锛坴1.3.3+锛?

鏀寔鍦?URL 涓洿鎺ユ寚瀹氭竻鏅板害锛屾棤闇€淇敼閰嶇疆鏂囦欢锛?

```
https://www.bilibili.com/video/BV18Cm8BHEeD/?qn=116
```

- URL 涓殑 `qn` 鍙傛暟浼?*瑕嗙洊**閰嶇疆鏂囦欢涓殑鍊?
- 濡傛灉 URL 鏈惡甯?`qn` 鍙傛暟锛屽垯浣跨敤閰嶇疆鏂囦欢鐨勯粯璁ゅ€?
- 绀轰緥锛歚?qn=116` 琛ㄧず涓嬭浇 1080P60 楂樺抚鐜囩増鏈?
- 鑱婂ぉ娑堟伅涓嫢閾炬帴鍚庡甫鏍囩偣锛屾彃浠朵細鑷姩娓呯悊鏈熬鏍囩偣鍚庡啀瑙ｆ瀽
- 鑻ラ摼鎺ヨ骞冲彴瑁佸壀瀵艰嚧鏌ヨ涓蹭涪澶憋紝鎻掍欢浼氫粠鍘熷娑堟伅涓厹搴曟彁鍙?`qn=`
- 鐭摼锛坄b23.tv`锛変細鍏堣烦杞啀瑙ｆ瀽 `qn`


---

## sessdata 鍜?buvid3 鑾峰彇鏂规硶

1. 浣跨敤 Chrome 娴忚鍣ㄦ墦寮€ B绔欎富椤点€?
2. 鎸変笅 `F12` 鎵撳紑寮€鍙戣€呭伐鍏枫€?
3. 鐐瑰嚮椤堕儴鐨?`Application`锛堝簲鐢級閫夐」鍗°€?
4. 鎸?`F5` 鍒锋柊椤甸潰銆?
5. 鍦ㄥ乏渚ф爮鎵惧埌 `Cookies` 骞跺睍寮€銆?
6. 鎵惧埌 `bilibili` 鐩稿叧鐨?Cookie 骞剁偣鍑汇€?
7. 鍦ㄥ彸渚х殑 `Value` 鍒楁壘鍒?`sessdata` 鍜?`buvid3` 鐨勫€笺€?
8. 灏嗚繖涓や釜鍊煎～鍏?`config.toml` 鏂囦欢涓搴旂殑浣嶇疆銆?

### 鍙傝€冩埅鍥?

- 寮€鍙戣€呭伐鍏锋墦寮€鐣岄潰  
  ![寮€鍙戣€呭伐鍏风晫闈(https://github.com/user-attachments/assets/d8b040de-a038-4772-b588-26df92d5ce73)

- Application 鏍? 
  ![Application 鏍廬(https://github.com/user-attachments/assets/0b8a5954-d6cd-47b6-95b9-126115203907)

- Cookie 浣嶇疆  
  ![Cookie 浣嶇疆](https://github.com/user-attachments/assets/4dc9c217-f78d-4d68-bb00-71ace2d3381f)

- bilibili Cookie  
  ![bilibili Cookie](https://github.com/user-attachments/assets/d82e3b15-64cd-490b-8eea-c6258ca0f6e2)

- sessdata 鍜?buvid3 绀轰緥  
  ![sessdata 鍜?buvid3](https://github.com/user-attachments/assets/607aa291-c927-4d00-8975-5e85fa0d1214)

---
### napcat閰嶇疆鍜宑onfig.toml
<img width="645" height="749" alt="image" src="https://github.com/user-attachments/assets/223c491f-8433-4c47-923a-c4c830c9e572" />
<img width="1186" height="807" alt="image" src="https://github.com/user-attachments/assets/10c79e45-048a-46c8-8d1d-ca7a4044070c" />
涓や釜绔彛瑕佷繚鎸佷竴鑷?

### 鍔″繀璁ょ湡濉啓config.toml!!!!!!


## 瀹屾垚鍚庣殑鏂囦欢澶圭粨鏋勭ず渚?
<img width="412" height="131" alt="image" src="https://github.com/user-attachments/assets/63ef60df-99f3-4c79-b124-da566fd15cd0" />
<img width="659" height="182" alt="image" src="https://github.com/user-attachments/assets/ddeb422f-b9fc-49b6-a652-866d06eb812c" />



