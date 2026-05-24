package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
        String[] box = new String[]{String.valueOf(p024)};
        alias(box);
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String p024) throws Exception {
        String query024 = "SELECT * FROM orders WHERE id = '" + p024 + "'";
        Statement st = conn.createStatement();
        st.executeQuery(query024);
    }

    private void alias(String[] b) {
        b[0] = b[0];  // aliasing-introducing extract
    }
}
