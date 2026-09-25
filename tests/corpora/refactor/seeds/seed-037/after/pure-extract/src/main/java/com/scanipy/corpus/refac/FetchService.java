package com.scanipy.corpus.refac;

import java.net.URL;
import java.net.HttpURLConnection;

public class FetchService {
    public int fetch(String input036) throws Exception {
        String left036 = "http://";
        String right036 = "/status";
        String value036 = _extracted_value(left036, input036, right036);
        URL url = new URL(value036);
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        return connection.getResponseCode();
    }

    private static String _extracted_value(String left036, String input036, String right036) {
        return left036 + input036 + right036;
    }
}
