package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String renamed0) throws Exception {
        String renamed1 = "SELECT * FROM orders WHERE id = '";
        String renamed2 = "'";
        String renamed3 = renamed1 + renamed0 + renamed2;
        Statement st = conn.createStatement();
        st.executeQuery(renamed3);
    }
}
