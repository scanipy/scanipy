package com.scanipy.corpus.refac;

import java.sql.Connection;
import java.sql.Statement;

public class OrderService {
    private final Connection conn;

    public OrderService(Connection conn) {
        this.conn = conn;
    }

    public void lookup(String input000) throws Exception {
        String left000 = "SELECT * FROM orders WHERE id = '";
        String right000 = "'";
        String[] box = new String[]{input000};
        _mutate(box);
        input000 = box[0];
        String value000 = left000 + input000 + right000;
        Statement st = conn.createStatement();
        st.executeQuery(value000);
    }

    private static void _mutate(String[] box) {
        box[0] = box[0] + "-alias";
    }
}
