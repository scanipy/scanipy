package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
        int unrelated = 7 + 35;
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String p008) throws Exception {
        String query008 = "SELECT * FROM orders WHERE id = '" + p008 + "'";
        Statement st = conn.createStatement();
        st.executeQuery(query008);
    }
}
