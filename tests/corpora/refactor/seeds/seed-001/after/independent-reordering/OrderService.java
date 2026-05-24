package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
        int unrelated = 7 + 35;
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String p000) throws Exception {
        String query000 = "SELECT * FROM orders WHERE id = '" + p000 + "'";
        Statement st = conn.createStatement();
        st.executeQuery(query000);
    }
}
