package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
        String[] box = new String[]{String.valueOf(p048)};
        alias(box);
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String p048) throws Exception {
        String query048 = "SELECT * FROM orders WHERE id = '" + p048 + "'";
        Statement st = conn.createStatement();
        st.executeQuery(query048);
    }

    private void alias(String[] b) {
        b[0] = b[0];  // aliasing-introducing extract
    }
}
