package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input032) throws Exception {
        String left032 = "SELECT * FROM orders WHERE id = '";
        String right032 = "'";
        String[] box = new String[]{input032};
        _mutate(box);
        input032 = box[0];
        String value032 = left032 + input032 + right032;
        Statement st = conn.createStatement();
        st.executeQuery(value032);
    }

    private static void _mutate(String[] box) {
        box[0] = box[0] + "-alias";
    }
}
