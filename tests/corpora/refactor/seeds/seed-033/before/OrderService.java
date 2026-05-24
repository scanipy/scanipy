package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String p032) throws Exception {
        String query032 = "SELECT * FROM orders WHERE id = '" + p032 + "'";
        Statement st = conn.createStatement();
        st.executeQuery(query032);
    }
}
