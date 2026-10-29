package com.medhatcoding.gptmi;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import org.json.JSONArray;
import org.json.JSONObject;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Locale;

public class MainActivity extends Activity {
    private final int navy = Color.rgb(16,42,67), teal = Color.rgb(26,174,159);
    private final int ink = Color.rgb(23,43,77), muted = Color.rgb(100,116,139);
    private final int page = Color.rgb(243,246,250), white = Color.WHITE;
    private LinearLayout root, content, nav;
    private JSONObject data;
    private int selected = 0;
    private boolean loading = false;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(navy);
        getWindow().setNavigationBarColor(navy);
        buildShell();
        loadData();
    }

    private void buildShell() {
        root = new LinearLayout(this); root.setOrientation(LinearLayout.VERTICAL); root.setBackgroundColor(page);
        setContentView(root);
        LinearLayout header = new LinearLayout(this); header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(18), dp(14), dp(18), dp(14)); header.setBackgroundColor(navy);
        header.setOrientation(LinearLayout.HORIZONTAL);
        LinearLayout brand = new LinearLayout(this); brand.setOrientation(LinearLayout.VERTICAL);
        TextView title = text("gpt-Mi", 24, white, true);
        TextView subtitle = text("ذكاء السوق المصري", 12, Color.rgb(185,215,232), false);
        brand.addView(title); brand.addView(subtitle);
        header.addView(brand, new LinearLayout.LayoutParams(0, -2, 1));
        Button refresh = new Button(this); refresh.setText("تحديث ↻"); refresh.setTextColor(white);
        refresh.setBackground(round(teal, 14)); refresh.setOnClickListener(v -> loadData());
        header.addView(refresh); root.addView(header);

        ScrollView scroll = new ScrollView(this); scroll.setFillViewport(true);
        content = new LinearLayout(this); content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(16), dp(16), dp(16), dp(22)); scroll.addView(content);
        root.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));

        nav = new LinearLayout(this); nav.setPadding(dp(8), dp(7), dp(8), dp(7));
        nav.setBackgroundColor(white); nav.setElevation(dp(8));
        String[] labels = {"الفرص", "السوق", "حول التطبيق"};
        for (int i=0;i<labels.length;i++) {
            final int tab = i;
            Button b = new Button(this); b.setText(labels[i]); b.setTextSize(12);
            b.setAllCaps(false); b.setOnClickListener(v -> { selected = tab; render(); });
            nav.addView(b, new LinearLayout.LayoutParams(0, dp(52), 1));
        }
        root.addView(nav);
    }

    private void loadData() {
        if (loading) return;
        loading = true;
        content.removeAllViews();
        content.addView(text("جارٍ تحميل أحدث تقرير…", 16, ink, true));
        new Thread(() -> {
            JSONObject result = null; String error = null; HttpURLConnection connection = null;
            try {
                URL url = new URL("https://raw.githubusercontent.com/MedhatCoding/gpt-Mi/main/data/signals/latest.json");
                connection = (HttpURLConnection) url.openConnection();
                connection.setConnectTimeout(12000); connection.setReadTimeout(12000);
                connection.setRequestProperty("Cache-Control", "no-cache");
                if (connection.getResponseCode() != 200) throw new Exception("HTTP " + connection.getResponseCode());
                StringBuilder body = new StringBuilder();
                java.io.BufferedReader reader = new java.io.BufferedReader(new java.io.InputStreamReader(connection.getInputStream(), "UTF-8"));
                String line; while ((line = reader.readLine()) != null) body.append(line);
                reader.close(); result = new JSONObject(body.toString());
            } catch (Exception e) { error = e.getMessage(); }
            finally { if (connection != null) connection.disconnect(); }
            final JSONObject fetched = result; final String failure = error;
            runOnUiThread(() -> {
                loading = false;
                if (fetched != null) data = fetched;
                if (failure != null && data == null) {
                    content.removeAllViews();
                    addText(content, "تعذر تحميل التقرير. تأكد من الإنترنت ثم اضغط تحديث.", 15, ink, false);
                } else render();
            });
        }).start();
    }

    private void render() {
        if (content == null) return;
        content.removeAllViews();
        if (selected == 2) { renderAbout(); return; }
        if (data == null) { addText(content, "لا توجد بيانات متاحة حاليًا.", 16, ink, true); return; }
        JSONObject market = data.optJSONObject("market"); if (market == null) market = new JSONObject();
        JSONObject regime = data.optJSONObject("regime"); if (regime == null) regime = new JSONObject();
        if (selected == 1) { renderMarket(market, regime); return; }

        addText(content, "ملخص السوق", 23, ink, true);
        addText(content, "بيانات الإغلاق: " + data.optString("data_date", "غير محدد"), 12, muted, false);
        LinearLayout hero = card(navy);
        addText(hero, "اتجاه السوق", 13, Color.rgb(185,215,232), false);
        LinearLayout headline = new LinearLayout(this); headline.setGravity(Gravity.CENTER_VERTICAL);
        TextView direction = text(regime.optString("label_ar", "غير متاح"), 24, white, true);
        TextView score = text(String.format(Locale.US, "%.0f/100", regime.optDouble("score")), 22, Color.rgb(115,226,208), true);
        headline.addView(direction, new LinearLayout.LayoutParams(0, -2, 1)); headline.addView(score);
        hero.addView(headline); addText(hero, "تغير المؤشر الداخلي: " + pct(market.optDouble("bench_change_1d")), 13, white, false);
        content.addView(hero);

        LinearLayout stats = new LinearLayout(this);
        LinearLayout.LayoutParams statParams = new LinearLayout.LayoutParams(-1, -2); statParams.topMargin = dp(10);
        stats.addView(statCard("تم تحليلها", data.optInt("analyzed") + " / " + data.optInt("universe_size")), new LinearLayout.LayoutParams(0,-2,1));
        View gap = new View(this); stats.addView(gap, new LinearLayout.LayoutParams(dp(10),1));
        JSONArray picks = data.optJSONArray("picks");
        stats.addView(statCard("فرص الشراء", String.valueOf(picks == null ? 0 : picks.length())), new LinearLayout.LayoutParams(0,-2,1));
        content.addView(stats, statParams);
        addText(content, "فرص الشراء المرشحة", 19, ink, true);
        if (picks == null || picks.length() == 0) addInfo("لا توجد فرص شراء في التقرير الحالي.", white);
        else for (int i=0;i<picks.length();i++) {
            JSONObject p = picks.optJSONObject(i); if (p != null && "BUY".equalsIgnoreCase(p.optString("signal"))) addPick(p);
        }
        JSONArray warnings = data.optJSONArray("warnings");
        if (warnings != null && warnings.length() > 0) {
            addText(content, "تنبيهات جودة البيانات", 18, ink, true);
            for (int i=0;i<warnings.length();i++) addInfo("⚠ " + warnings.optString(i), Color.rgb(255,246,229));
        }
        addText(content, "آخر تحديث: " + data.optString("generated_at", "غير متاح"), 11, muted, false);
        addInfo("التحليل أداة مساعدة وليس ضمانًا للربح أو فتوى شرعية.", white);
    }

    private void renderMarket(JSONObject market, JSONObject regime) {
        addText(content, "صورة السوق", 23, ink, true);
        addInfo("حالة السوق: " + regime.optString("label_ar", "غير متاح") + " — درجة " + String.format(Locale.US, "%.0f", regime.optDouble("score")) + "/100", white);
        addInfo("تغير المؤشر الداخلي: " + pct(market.optDouble("bench_change_1d")), white);
        addInfo("عدد الأسهم المحللة: " + data.optInt("analyzed") + " من " + data.optInt("universe_size"), white);
        addText(content, "الأكثر ارتفاعًا", 18, ink, true);
        addMarketRows(market.optJSONArray("top_gainers"), true);
        addText(content, "الأكثر انخفاضًا", 18, ink, true);
        addMarketRows(market.optJSONArray("top_losers"), false);
    }

    private void addMarketRows(JSONArray rows, boolean positive) {
        if (rows == null || rows.length() == 0) { addInfo("لا توجد بيانات.", white); return; }
        for (int i=0;i<rows.length();i++) {
            JSONObject x = rows.optJSONObject(i); if (x == null) continue;
            addInfo(x.optString("code") + " — " + x.optString("name") + "   " + pct(x.optDouble("ret1")),
                positive ? Color.rgb(234,248,241) : Color.rgb(255,238,238));
        }
    }

    private void addPick(JSONObject p) {
        LinearLayout box = card(white);
        LinearLayout top = new LinearLayout(this); top.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout company = new LinearLayout(this); company.setOrientation(LinearLayout.VERTICAL);
        company.addView(text(p.optString("name", p.optString("code")), 17, ink, true));
        company.addView(text(p.optString("code"), 12, muted, false));
        top.addView(company, new LinearLayout.LayoutParams(0,-2,1));
        LinearLayout points = new LinearLayout(this); points.setOrientation(LinearLayout.VERTICAL); points.setGravity(Gravity.END);
        points.addView(text("شراء", 12, Color.rgb(22,132,91), true));
        points.addView(text(String.format(Locale.US, "%.0f/100", p.optDouble("score")), 20, teal, true));
        top.addView(points); box.addView(top);
        addPair(box, "السعر", num(p.optDouble("close")), "نطاق الدخول", num(p.optDouble("entry_low")) + " – " + num(p.optDouble("entry_high")));
        addPair(box, "وقف الخسارة", num(p.optDouble("stop")), "الهدف الأول", num(p.optDouble("t1")));
        addPair(box, "الهدف الثاني", num(p.optDouble("t2")), "RSI", num(p.optDouble("rsi")));
        addText(box, joinArray(p.optJSONArray("why"), "سبب الترشيح: "), 13, ink, false);
        String caution = joinArray(p.optJSONArray("cautions"), "المخاطر: ");
        if (!caution.isEmpty()) addText(box, caution, 12, Color.rgb(181,71,71), false);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1,-2); lp.bottomMargin = dp(12); content.addView(box, lp);
    }

    private void addPair(LinearLayout parent, String l1, String v1, String l2, String v2) {
        LinearLayout row = new LinearLayout(this); row.setOrientation(LinearLayout.HORIZONTAL);
        LinearLayout a = valueTile(l1,v1), b = valueTile(l2,v2);
        row.addView(a, new LinearLayout.LayoutParams(0,-2,1));
        View gap = new View(this); row.addView(gap, new LinearLayout.LayoutParams(dp(8),1));
        row.addView(b, new LinearLayout.LayoutParams(0,-2,1));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1,-2); lp.topMargin = dp(8); parent.addView(row, lp);
    }
    private LinearLayout valueTile(String label, String value) {
        LinearLayout box = new LinearLayout(this); box.setOrientation(LinearLayout.VERTICAL); box.setPadding(dp(10),dp(8),dp(10),dp(8)); box.setBackground(round(page,12));
        addText(box,label,11,muted,false); addText(box,value,14,ink,true); return box;
    }
    private LinearLayout statCard(String label, String value) {
        LinearLayout box = card(white); addText(box,label,12,muted,false); addText(box,value,22,ink,true); return box;
    }
    private void renderAbout() {
        addText(content, "عن gpt-Mi", 23, ink, true);
        addInfo("تطبيق Android بواجهة أصلية مصممة للهاتف، وليس صفحة Streamlit داخل WebView.", white);
        addInfo("يعرض أحدث تقرير منشور في مستودع gpt-Mi. يلزم اتصال بالإنترنت لجلب البيانات.", white);
        addInfo("التحليل الفني أداة مساعدة وليس توصية استثمارية مضمونة.", white);
        addInfo("التوافق مع الشريعة يعتمد على منهجية الفلترة ومصدرها وتاريخ مراجعتها؛ هذه الشاشة ليست فتوى شرعية مستقلة.", white);
    }
    private void addInfo(String value, int color) {
        LinearLayout box = card(color); addText(box,value,14,ink,false);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1,-2); lp.bottomMargin = dp(10); content.addView(box,lp);
    }
    private LinearLayout card(int color) {
        LinearLayout box = new LinearLayout(this); box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(15),dp(14),dp(15),dp(14)); box.setBackground(round(color,18));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1,-2); lp.bottomMargin = dp(12);
        box.setElevation(dp(1)); return box;
    }
    private void addText(LinearLayout parent, String value, int size, int color, boolean bold) {
        TextView t = text(value,size,color,bold);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(-1,-2); lp.topMargin = dp(4); lp.bottomMargin = dp(4); parent.addView(t,lp);
    }
    private TextView text(String value, int size, int color, boolean bold) {
        TextView t = new TextView(this); t.setText(value); t.setTextSize(size); t.setTextColor(color);
        t.setGravity(Gravity.RIGHT); t.setTextDirection(View.TEXT_DIRECTION_RTL);
        if (bold) t.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        t.setLineSpacing(dp(2),1.0f); return t;
    }
    private GradientDrawable round(int color, int radius) {
        GradientDrawable d = new GradientDrawable(); d.setColor(color); d.setCornerRadius(dp(radius)); return d;
    }
    private int dp(int v) { return (int)(v * getResources().getDisplayMetrics().density + 0.5f); }
    private String num(double v) { return !Double.isFinite(v) || v == 0 ? "—" : String.format(Locale.US,"%.2f",v); }
    private String pct(double v) { return String.format(Locale.US,"%+.2f%%",v); }
    private String joinArray(JSONArray a, String prefix) {
        if (a == null || a.length() == 0) return "";
        StringBuilder s = new StringBuilder(prefix);
        for (int i=0;i<a.length();i++) { if (i>0) s.append("، "); s.append(a.optString(i)); }
        return s.toString();
    }
}
