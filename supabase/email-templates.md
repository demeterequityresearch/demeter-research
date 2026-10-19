# Supabase 메일 문구 (한국어)

Supabase 대시보드 → Authentication → Emails → Templates 탭에서 종류별로 Subject와 Body(Message body)를 아래로 바꾸고 Save.
`{{ .ConfirmationURL }}`, `{{ .Email }}`, `{{ .NewEmail }}`은 Supabase가 채우는 자리이니 그대로 둔다.

---

## 1. Confirm sign up (가입 인증)

**Subject**

```
[알파인사이트] 이메일 인증을 완료해 주세요
```

**Body**

```html
<div style="font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#13211C;line-height:1.7">
  <p style="font-size:13px;letter-spacing:.12em;color:#87642F;margin:0 0 8px">ALPHA INSIGHT</p>
  <h2 style="font-size:20px;margin:0 0 16px">이메일 인증</h2>
  <p>알파인사이트(Alpha Insight)에 가입해 주셔서 감사합니다.<br>아래 버튼을 누르면 가입이 완료됩니다.</p>
  <p style="margin:24px 0">
    <a href="{{ .ConfirmationURL }}" style="display:inline-block;padding:12px 24px;background:#0E3B30;color:#EDE6D6;text-decoration:none;border-radius:8px">이메일 인증하기</a>
  </p>
  <p style="font-size:13px;color:#56645E">링크는 1시간 동안 유효합니다. 직접 가입하지 않으셨다면 이 메일을 무시해 주세요.</p>
</div>
```

## 2. Reset password (비밀번호 재설정)

**Subject**

```
[알파인사이트] 비밀번호 재설정 안내
```

**Body**

```html
<div style="font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#13211C;line-height:1.7">
  <p style="font-size:13px;letter-spacing:.12em;color:#87642F;margin:0 0 8px">ALPHA INSIGHT</p>
  <h2 style="font-size:20px;margin:0 0 16px">비밀번호 재설정</h2>
  <p>비밀번호 재설정을 요청하셨습니다.<br>아래 버튼을 누르면 새 비밀번호를 정할 수 있습니다.</p>
  <p style="margin:24px 0">
    <a href="{{ .ConfirmationURL }}" style="display:inline-block;padding:12px 24px;background:#0E3B30;color:#EDE6D6;text-decoration:none;border-radius:8px">새 비밀번호 정하기</a>
  </p>
  <p style="font-size:13px;color:#56645E">링크는 1시간 동안 유효합니다. 요청하지 않으셨다면 이 메일을 무시해 주세요. 비밀번호는 바뀌지 않습니다.</p>
</div>
```

## 3. Change email address (이메일 변경, 지금은 쓰지 않지만 함께 바꿔 둠)

**Subject**

```
[알파인사이트] 이메일 변경 확인
```

**Body**

```html
<div style="font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#13211C;line-height:1.7">
  <p style="font-size:13px;letter-spacing:.12em;color:#87642F;margin:0 0 8px">ALPHA INSIGHT</p>
  <h2 style="font-size:20px;margin:0 0 16px">이메일 변경 확인</h2>
  <p>회원 이메일을 {{ .Email }} 에서 {{ .NewEmail }} 으로 바꾸는 요청을 받았습니다.<br>아래 버튼을 누르면 변경이 완료됩니다.</p>
  <p style="margin:24px 0">
    <a href="{{ .ConfirmationURL }}" style="display:inline-block;padding:12px 24px;background:#0E3B30;color:#EDE6D6;text-decoration:none;border-radius:8px">이메일 변경 확인</a>
  </p>
  <p style="font-size:13px;color:#56645E">요청하지 않으셨다면 이 메일을 무시해 주세요.</p>
</div>
```
