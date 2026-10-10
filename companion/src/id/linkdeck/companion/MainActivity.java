package id.linkdeck.companion;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.provider.Settings;
import android.util.TypedValue;
import android.view.View;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** Layar sederhana: penjelasan, status akses notifikasi, jumlah sambungan LinkDeck. */
public class MainActivity extends Activity {
    private TextView status;
    private TextView clients;

    @Override
    protected void onCreate(Bundle saved) {
        super.onCreate(saved);
        int pad = dp(20);
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText(R.string.app_name);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 24);
        title.setTextColor(Color.rgb(29, 32, 48));
        box.addView(title);

        TextView intro = text(getString(R.string.intro));
        box.addView(intro);

        status = text("");
        status.setTextSize(TypedValue.COMPLEX_UNIT_SP, 17);
        box.addView(status);

        clients = text("");
        box.addView(clients);

        Button open = new Button(this);
        open.setText(R.string.open_settings);
        open.setOnClickListener(new View.OnClickListener() {
            @Override public void onClick(View v) {
                try {
                    startActivity(new Intent("android.settings.ACTION_NOTIFICATION_LISTENER_SETTINGS"));
                } catch (Exception e) {
                    startActivity(new Intent(Settings.ACTION_SETTINGS));
                }
            }
        });
        box.addView(open);

        TextView privacy = text(getString(R.string.privacy));
        privacy.setTextSize(TypedValue.COMPLEX_UNIT_SP, 13);
        box.addView(privacy);

        ScrollView sv = new ScrollView(this);
        sv.addView(box);
        setContentView(sv);
    }

    @Override
    protected void onResume() {
        super.onResume();
        boolean on = accessEnabled();
        status.setText(on ? R.string.access_on : R.string.access_off);
        status.setTextColor(on ? Color.rgb(27, 120, 70) : Color.rgb(180, 60, 40));
        clients.setText(getString(R.string.clients, NotifService.clientCount));
    }

    private boolean accessEnabled() {
        String flat = Settings.Secure.getString(getContentResolver(), "enabled_notification_listeners");
        if (flat == null) return false;
        ComponentName me = new ComponentName(this, NotifService.class);
        for (String part : flat.split(":")) {
            ComponentName cn = ComponentName.unflattenFromString(part);
            if (me.equals(cn)) return true;
        }
        return false;
    }

    private TextView text(String s) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        t.setPadding(0, dp(12), 0, 0);
        t.setTextColor(Color.rgb(60, 64, 80));
        return t;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }
}
